"""Opt-in verification with a dedicated, disposable Home Assistant test instance."""
import json
import os
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import websocket

from app.config import Config
from app.energy import EnergyLedger
from app.statistics import StatisticsImporter, build_statistics
from test_daily_statistics import sample


@unittest.skipUnless(os.getenv('SEWEB_TEST_HA_TOKEN_FILE'), 'Dedicated HA test instance not configured')
class HomeAssistantStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.url = os.environ.get('SEWEB_TEST_HA_URL', 'ws://127.0.0.1:58123/api/websocket')
        # Never run this test against an arbitrary user instance.
        self.assertIn(urlsplit(self.url).hostname, {'127.0.0.1', 'localhost', 'seweb-history-ha'})
        self.token = json.loads(Path(os.environ['SEWEB_TEST_HA_TOKEN_FILE']).read_text())['access_token']
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(data_dir=Path(self.directory.name), plant_name='Statistics test '+uuid.uuid4().hex)
        self.ledger = EnergyLedger(self.config)
        self.importer = StatisticsImporter(self.config, url=self.url, token=self.token)
        self.socket = websocket.create_connection(self.url, timeout=20, suppress_origin=True)
        self.addCleanup(self.socket.close)
        self.assertEqual(json.loads(self.socket.recv())['type'], 'auth_required')
        self.socket.send(json.dumps({'type':'auth','access_token':self.token}))
        self.assertEqual(json.loads(self.socket.recv())['type'], 'auth_ok')
        self.sequence = 0

    def command(self, *, allow_not_found=False, **message):
        self.sequence += 1
        self.socket.send(json.dumps(dict(message, id=self.sequence)))
        reply = json.loads(self.socket.recv())
        if allow_not_found and reply.get('error', {}).get('code') == 'not_found':
            return None
        self.assertTrue(reply.get('success'), 'Dedicated HA rejected test command')
        return reply.get('result')

    def test_actual_recorder_replay_correction_dst_and_energy_selection(self):
        self.ledger.apply([sample('2025-10-25', 10)], observed_at=datetime.fromisoformat('2025-10-25T12:00:00+02:00'))
        self.ledger.apply([sample('2025-10-25', 12), sample('2025-10-26', 20), sample('2025-10-27', 3)],
                          observed_at=datetime.fromisoformat('2025-10-27T10:30:00+01:00'))
        now = datetime.fromisoformat('2025-10-27T10:30:00+01:00')
        self.assertEqual(self.importer.sync(self.ledger.state, now=now), 'ok')
        self.assertEqual(self.importer.sync(self.ledger.state, now=now), 'ok')
        batches = build_statistics(self.config, self.ledger.state, now)
        ids = [b['metadata']['statistic_id'] for b in batches]
        def days():
            result = self.command(type='recorder/statistics_during_period',
                                  start_time='2025-10-24T00:00:00+02:00', end_time='2025-10-28T00:00:00+01:00',
                                  statistic_ids=ids, period='day', types=['sum','change'])
            return {datetime.fromtimestamp(row['start']/1000,ZoneInfo('Europe/Berlin')).date().isoformat(): row['change']
                    for row in result[ids[0]]}
        changes = days()
        for day, expected in [('2025-10-25',12),('2025-10-26',20),('2025-10-27',3)]:
            self.assertAlmostEqual(changes[day], expected)
        self.ledger.apply([sample('2025-10-26', 21), sample('2025-10-27', 3)],
                          observed_at=datetime.fromisoformat('2025-10-27T10:45:00+01:00'))
        self.assertEqual(self.importer.sync(self.ledger.state, now=now), 'ok')
        changes = days()
        self.assertAlmostEqual(changes['2025-10-26'], 21)
        self.assertAlmostEqual(changes['2025-10-27'], 3)
        metadata = self.command(type='recorder/list_statistic_ids', statistic_type='sum')
        selected = [item for item in metadata if item['statistic_id'] in ids]
        self.assertEqual(len(selected), 5)
        self.assertTrue(all(item['unit_class']=='energy' for item in selected))
        # Save/validate/restore energy preferences only on the dedicated test HA.
        old = self.command(type='energy/get_prefs', allow_not_found=True) or {'energy_sources':[], 'device_consumption':[]}
        try:
            self.command(type='energy/save_prefs', energy_sources=[
                {'type':'solar', 'stat_energy_from':ids[0]},
                {'type':'grid', 'stat_energy_from':ids[1],
                 'stat_energy_to':ids[2], 'cost_adjustment_day':0}], device_consumption=[])
            result = self.command(type='energy/validate')
            self.assertFalse(result['energy_sources'][0], 'Solar statistic rejected by energy dashboard')
            self.assertFalse(result['energy_sources'][1], 'Grid statistics rejected by energy dashboard')
        finally:
            self.command(type='energy/save_prefs', **old)
