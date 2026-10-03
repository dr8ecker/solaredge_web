# Copyright (c) 2026 8ecker.de
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.config import Config
from app.energy import EnergyLedger, ENERGY_KEYS, LedgerError
from app.models import DayEnergy
from app.parser import ValueParser, ParseError
from app.mqtt import MqttPublisher


def sample(day, base):
    return DayEnergy(date.fromisoformat(day), {k:Decimal(str(base)) for k in ENERGY_KEYS}, {k:Decimal('.01') for k in ENERGY_KEYS})


class ParserTests(unittest.TestCase):
    def test_normalizes_real_units_and_decimal_formats(self):
        for raw, unit, expected in [('5.43 kW','W','5430'),('5,43 kW','W','5430'),
                                     ('543 W','W','543'),('7.2 MWh','kWh','7200'),
                                     ('18,4 kWh','kWh','18.4'),('1.234,56 Wh','kWh','1.23456'),
                                     ('1,234.56 kWh','kWh','1234.56'),('20˚C','°C','20'),
                                     ('85 %','%','85'),('230 V','V','230'),('50 Hz','Hz','50')]:
            with self.subTest(raw=raw):
                self.assertEqual(ValueParser.parse(raw, unit).value, Decimal(expected))

    def test_rejects_missing_negative_ambiguous_and_impossible_values(self):
        for raw, unit in [('Loading','W'),('-1 kWh','kWh'),('5 kW 16 kW','W'),
                          ('200 °C','°C'),('101%','%'),('1.2.3 kWh','kWh')]:
            with self.subTest(raw=raw), self.assertRaises(ParseError):
                ValueParser.parse(raw, unit)

    def test_ignores_specific_yield_and_carries_display_resolution(self):
        self.assertEqual(ValueParser.parse('Produzierte Energie 51.7 kWh Bestimmter Ertrag 2.65 Wh/Wp','kWh').resolution, Decimal('.1'))
        self.assertEqual(ValueParser.parse('103 MWh','kWh').resolution, Decimal('1000'))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(data_dir=Path(self.directory.name))

    def test_restart_retry_midnight_and_last_half_hour_are_counted_once(self):
        ledger = EnergyLedger(self.config)
        ledger.apply([sample('2026-10-02',10)])
        totals,_ = ledger.apply([sample('2026-10-02',12)])
        self.assertEqual(totals['pv_energy_total'],12)
        ledger = EnergyLedger(self.config)
        self.assertEqual(ledger.needed_days(date(2026,10,3)),[date(2026,10,2)])
        # Vortag grows from12 to13 after finalpoll; Today is already2.
        totals,_ = ledger.apply([sample('2026-10-02',13),sample('2026-10-03',2)])
        self.assertEqual(totals['pv_energy_total'],15)
        totals,_ = EnergyLedger(self.config).apply([sample('2026-10-02',13),sample('2026-10-03',2)])
        self.assertEqual(totals['pv_energy_total'],15)

    def test_decrease_does_not_reset_or_double_count(self):
        ledger = EnergyLedger(self.config)
        ledger.apply([sample('2026-10-02',12)])
        totals,warnings = ledger.apply([sample('2026-10-02',11.9)])
        self.assertEqual(totals['pv_energy_total'],12)
        self.assertTrue(warnings)

    def test_missing_and_corrupt_ledger_never_publish_zero(self):
        ledger = EnergyLedger(self.config)
        ledger.apply([sample('2026-10-02',12)])
        ledger.path.write_text('{')
        with self.assertRaises(LedgerError):
            EnergyLedger(self.config)
        ledger.path.unlink()
        with self.assertRaises(LedgerError):
            EnergyLedger(self.config)

    def test_long_outage_is_bounded_and_gap_is_visible(self):
        ledger = EnergyLedger(self.config)
        ledger.apply([sample('2026-09-01',1)])
        needed = ledger.needed_days(date(2026,10,2))
        self.assertEqual(len(needed),7)
        totals,_ = ledger.apply([sample(d.isoformat(),1) for d in needed] + [sample('2026-10-02',1)])
        self.assertEqual(totals['pv_energy_total'],9)
        self.assertTrue(ledger.state['gaps'])

    def test_wrong_plant_and_backward_clock_rejected(self):
        ledger = EnergyLedger(self.config)
        ledger.apply([sample('2026-10-02',12)])
        with self.assertRaises(LedgerError):
            EnergyLedger(Config(plant_name='Another plant',data_dir=self.config.data_dir))
        with self.assertRaises(LedgerError):
            ledger.needed_days(date(2026,10,1))


class DiscoveryMetadataTests(unittest.TestCase):
    def test_energy_dashboard_metadata_and_no_battery(self):
        publisher = MqttPublisher(Config())
        from app.mqtt import SENSORS
        self.assertFalse(any('battery' in key for key in SENSORS))
        for key in ('pv_energy_total','grid_import_energy_total','grid_export_energy_total'):
            config = publisher.config_payload(key)
            self.assertEqual(config['state_class'],'total')
            self.assertEqual(config['device_class'],'energy')
            self.assertEqual(config['unit_of_measurement'],'kWh')
            self.assertNotIn('last_reset_value_template',config)
        self.assertNotIn('state_class',publisher.config_payload('energy_today'))

    def test_omitted_live_fields_are_unavailable_not_zero(self):
        publisher = MqttPublisher(Config())
        publisher.update({'pv_power':1000,'grid_export_power':800},solar_success=True)
        publisher.update({'pv_power':2000},solar_success=True)
        self.assertNotIn('grid_export_power',publisher.present)
        self.assertEqual(publisher.cache['grid_export_power'],800)
