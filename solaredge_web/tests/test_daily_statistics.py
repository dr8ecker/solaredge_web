# Copyright (c) 2026 8ecker.de
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app.config import Config
from app.energy import EnergyLedger, ENERGY_KEYS, LedgerError, daily_values
from app.models import DayEnergy
from app.mqtt import MqttPublisher
from app.statistics import StatisticsError, StatisticsImporter, build_statistics


def sample(day, value):
    return DayEnergy(date.fromisoformat(day), {k: Decimal(str(value)) for k in ENERGY_KEYS},
                     {k: Decimal('.01') for k in ENERGY_KEYS})


class DailyValuesTests(unittest.TestCase):
    def test_daily_balances_and_ratios_use_energy_not_instantaneous_power(self):
        item = sample('2026-10-02', 0)
        item.values.update(pv_energy=Decimal(20), consumption_energy=Decimal(15),
                           self_consumption_energy=Decimal(10), grid_import_energy=Decimal(5),
                           grid_export_energy=Decimal(10))
        values = daily_values(item)
        self.assertEqual(values['energy_today'], 20)
        self.assertEqual(values['consumption_energy_today'], 15)
        self.assertEqual(values['autarky_today'], 66.7)
        self.assertEqual(values['self_consumption_ratio_today'], 50)

    def test_zero_denominators_are_unavailable_but_valid_zero_ratios_remain_zero(self):
        item = sample('2026-10-02', 0)
        values = daily_values(item)
        self.assertNotIn('autarky_today', values)
        self.assertNotIn('self_consumption_ratio_today', values)
        item.values['consumption_energy'] = Decimal(2)
        self.assertEqual(daily_values(item)['autarky_today'], 0)


class FreshnessTests(unittest.TestCase):
    def test_success_ages_without_another_scrape_and_recovers(self):
        p = MqttPublisher(Config(poll_interval=600))
        self.assertEqual(p.config.health_max_age, 1800)
        p.update({'scraper_status': 'connected'}, solar_success=True)
        self.assertEqual(p.freshness(p.last_success + 1799), 'fresh')
        self.assertEqual(p.freshness(p.last_success + 1801), 'stale')
        p.update({'scraper_status': 'error'})
        self.assertEqual(p.freshness(), 'retrying')
        p.unavailable()
        self.assertEqual(p.freshness(), 'error')
        p.update({'scraper_status': 'connected'}, solar_success=True)
        self.assertEqual(p.freshness(), 'fresh')

    def test_login_attention_is_not_hidden_by_old_success(self):
        p = MqttPublisher(Config())
        for status in ('manual_login_required', 'terms_confirmation_required'):
            p.update({'scraper_status': status})
            self.assertEqual(p.freshness(p.created_at + 10000), status)

    def test_daily_values_expire_at_local_midnight_without_publishing_zero(self):
        p = MqttPublisher(Config())
        p.client = Mock(is_connected=Mock(return_value=True))
        now = datetime.now(ZoneInfo(p.config.site_timezone))
        p.update({'energy_today': 58.2, 'energy_date': now.date().isoformat()}, solar_success=True)
        self.assertEqual(p.validity_cache['energy_today'], 'online')
        with patch('app.mqtt.datetime') as clock:
            clock.now.return_value = now + timedelta(days=1)
            p.publish_availability()
        self.assertEqual(p.validity_cache['energy_today'], 'offline')
        self.assertEqual(p.cache['energy_today'], 58.2)


class StatisticsPlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(data_dir=Path(self.directory.name))
        self.ledger = EnergyLedger(self.config)

    def build(self, now):
        return build_statistics(self.config, self.ledger.state, datetime.fromisoformat(now))

    def test_outage_and_late_correction_stay_on_source_day_with_stable_later_sums(self):
        self.ledger.apply([sample('2026-10-01', 10)], observed_at=datetime.fromisoformat('2026-10-01T12:15:00+02:00'))
        self.ledger.apply([sample('2026-10-01', 12), sample('2026-10-02', 20), sample('2026-10-03', 3)],
                          observed_at=datetime.fromisoformat('2026-10-03T10:30:00+02:00'))
        batches = self.build('2026-10-03T10:30:00+02:00')
        rows = {r['start']: r['sum'] for r in batches[0]['stats']}
        self.assertEqual(rows['2026-09-30T21:00:00+00:00'], 0)  # Baseline before Oct 1.
        self.assertEqual(rows['2026-10-01T10:00:00+00:00'], 10)
        self.assertEqual(rows['2026-10-01T21:00:00+00:00'], 12)
        self.assertEqual(rows['2026-10-02T20:00:00+00:00'], 12)
        self.assertEqual(rows['2026-10-02T21:00:00+00:00'], 32)
        self.assertEqual(rows['2026-10-03T08:00:00+00:00'], 35)
        self.ledger = EnergyLedger(self.config)
        self.assertEqual(self.build('2026-10-03T10:30:00+02:00'), batches)
        # A correction changes the original day AND following absolute sums.
        self.ledger.apply([sample('2026-10-02', 21), sample('2026-10-03', 3)],
                          observed_at=datetime.fromisoformat('2026-10-03T10:45:00+02:00'))
        rows = {r['start']: r['sum'] for r in self.build('2026-10-03T10:45:00+02:00')[0]['stats']}
        self.assertEqual(rows['2026-10-02T21:00:00+00:00'], 33)
        self.assertEqual(rows['2026-10-03T08:00:00+00:00'], 36)

    def test_dst_days_contain_23_and_25_hours_and_exact_daily_energy(self):
        for day, expected in [('2026-03-29', 23), ('2026-10-25', 25)]:
            state = {'carry': {k:'0' for k in ENERGY_KEYS}, 'days': {day:{k:'15' for k in ENERGY_KEYS}}}
            now = datetime.combine(date.fromisoformat(day) + timedelta(days=1), datetime.min.time(), ZoneInfo('Europe/Berlin'))
            rows = build_statistics(self.config, state, now)[0]['stats']
            self.assertEqual(len(rows), expected+1)
            self.assertEqual(len({r['start'] for r in rows}), expected+1)
            self.assertEqual(rows[-1]['sum']-rows[0]['sum'], 15)

    def test_upgrade_preserves_existing_ledger_and_ids_do_not_target_mqtt_sensors(self):
        self.ledger.apply([sample('2026-10-02', 58.2)])
        state = json.loads(self.ledger.path.read_text())
        state.pop('hours')
        self.ledger.path.write_text(json.dumps(state))
        upgraded = EnergyLedger(self.config)
        self.assertEqual(upgraded.state['days']['2026-10-02']['pv_energy'], '58.2')
        batches = build_statistics(self.config, upgraded.state, datetime.fromisoformat('2026-10-03T10:00:00+02:00'))
        for batch in batches:
            self.assertTrue(batch['metadata']['statistic_id'].startswith('solaredge_web:'))
            self.assertEqual(batch['metadata']['mean_type'], 0)
            self.assertEqual(batch['stats'][-1]['sum'], 58.2)

    def test_invalid_or_backwards_observation_cannot_change_persistent_totals(self):
        self.ledger.apply([sample('2026-10-02', 10)], observed_at=datetime.fromisoformat('2026-10-02T12:00:00+02:00'))
        before = self.ledger.path.read_bytes()
        for stamp in ['2026-10-02T11:00:00+02:00', '2026-10-03T12:00:00+02:00', '2026-10-02T12:00:00']:
            with self.assertRaises(LedgerError):
                self.ledger.apply([sample('2026-10-02', 11)], observed_at=datetime.fromisoformat(stamp))
            self.assertEqual(self.ledger.path.read_bytes(), before)

    def test_compaction_retains_absolute_sum_and_discards_old_hourly_points(self):
        self.ledger.apply([sample('2026-08-01', 10)], observed_at=datetime.fromisoformat('2026-08-01T12:00:00+02:00'))
        self.ledger.apply([sample('2026-10-02', 4)], observed_at=datetime.fromisoformat('2026-10-02T12:00:00+02:00'))
        self.assertNotIn('2026-08-01', self.ledger.state['hours'])
        rows = self.build('2026-10-02T12:30:00+02:00')[0]['stats']
        self.assertEqual(rows[0]['sum'], 10)
        self.assertEqual(rows[-1]['sum'], 14)

    def test_partial_hour_timezone_is_rejected_instead_of_misdated(self):
        self.ledger.apply([sample('2026-10-02', 1)])
        with self.assertRaises(StatisticsError):
            build_statistics(Config(site_timezone='Asia/Kathmandu'), self.ledger.state,
                             datetime.fromisoformat('2026-10-03T12:00:00+00:00'))


class ImporterTests(unittest.TestCase):
    def test_disabled_and_standalone_need_no_connection(self):
        self.assertEqual(StatisticsImporter(Config(history_import=False), token='').sync({}), 'disabled')
        self.assertEqual(StatisticsImporter(Config(), token='').sync({}), 'supervisor_required')

    def test_server_error_never_exposes_response_or_token(self):
        state={'days': {'2026-10-02':{k:'1' for k in ENERGY_KEYS}}, 'carry':{k:'0' for k in ENERGY_KEYS}}
        connection=Mock()
        connection.recv.side_effect=[json.dumps({'type':'auth_required'}), json.dumps({'type':'auth_invalid','message':'PRIVATE'})]
        with patch('websocket.create_connection',return_value=connection):
            with self.assertRaises(StatisticsError) as caught:
                StatisticsImporter(Config(), token='PRIVATE').sync(state,now=datetime.fromisoformat('2026-10-03T12:00:00+00:00'))
        self.assertNotIn('PRIVATE',str(caught.exception))
        connection.close.assert_called_once()
