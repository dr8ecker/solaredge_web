"""Day-correct external HA statistics; never writes MQTT sensor statistics.

Observed increases stay in their observation hour. Unobserved historical energy
and late corrections go into the last hour of their source day. Full bounded
windows are replaced idempotently so a correction also fixes later cumulative sums.
"""

import json
import os
import time
from datetime import date, datetime, time as day_time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .energy import ENERGY_KEYS, identity

NAMES = {'pv_energy': 'PV-Erzeugung', 'grid_import_energy': 'Netzbezug',
         'grid_export_energy': 'Einspeisung', 'consumption_energy': 'Hausverbrauch',
         'self_consumption_energy': 'PV-Eigenverbrauch'}


class StatisticsError(RuntimeError):
    """Fixed public error categories; never include token or server response text."""


def build_statistics(config, state, now):
    if now.tzinfo is None:
        raise StatisticsError('Statistics clock must include timezone')
    if not state['days']:
        return []
    zone = ZoneInfo(config.site_timezone)
    current_hour = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    today = now.astimezone(zone).date()
    first = date.fromisoformat(min(state['days']))
    baseline = datetime.combine(first, day_time(), zone).astimezone(timezone.utc) - timedelta(hours=1)
    carry = {key: Decimal(state['carry'][key]) for key in ENERGY_KEYS}
    series = {key: [{'start': baseline.isoformat(), 'sum': float(carry[key]), 'state': float(carry[key])}]
              for key in ENERGY_KEYS}
    for day_text, totals in sorted(state['days'].items()):
        day = date.fromisoformat(day_text)
        if day > today:
            raise StatisticsError('Ledger contains a future date')
        start = datetime.combine(day, day_time(), zone).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), day_time(), zone).astimezone(timezone.utc)
        if start.minute or end.minute:
            raise StatisticsError('History requires timezone boundaries on whole UTC hours')
        # UTC iteration handles both occurrences of the autumn DST hour.
        last = min(end - timedelta(hours=1), current_hour)
        observations = state.get('hours', {}).get(day_text, {})
        current = {key: Decimal(0) for key in ENERGY_KEYS}
        hour = start
        while hour <= last:
            if row := observations.get(hour.isoformat()):
                current = {key: Decimal(row[key]) for key in ENERGY_KEYS}
            if hour == last:
                current = {key: Decimal(totals[key]) for key in ENERGY_KEYS}
            for key in ENERGY_KEYS:
                total = float(carry[key] + current[key])
                series[key].append({'start': hour.isoformat(), 'sum': total, 'state': total})
            hour += timedelta(hours=1)
        for key in ENERGY_KEYS:
            carry[key] += Decimal(totals[key])
    return [{'metadata': {'statistic_id': f'solaredge_web:seweb_{identity(config)}_{key}',
                          'source': 'solaredge_web', 'name': f'SolarEdge {NAMES[key]} · Tagesgenau ({config.plant_name})',
                          'unit_of_measurement': 'kWh', 'unit_class': 'energy',
                          'mean_type': 0, 'has_sum': True}, 'stats': series[key]}
            for key in ENERGY_KEYS]


class StatisticsImporter:
    def __init__(self, config, *, url='ws://supervisor/core/websocket', token=None):
        self.config = config
        self.url = url
        self.token = token if token is not None else os.getenv('SUPERVISOR_TOKEN', '')

    def sync(self, state, *, now=None):
        if not self.config.history_import:
            return 'disabled'
        if not self.token:
            return 'supervisor_required'
        batches = build_statistics(self.config, state, now or datetime.now(timezone.utc))
        if not batches:
            return 'waiting'
        import websocket
        socket = None
        try:
            socket = websocket.create_connection(self.url, timeout=15, suppress_origin=True)
            if json.loads(socket.recv()).get('type') != 'auth_required':
                raise StatisticsError('History authentication unavailable')
            socket.send(json.dumps({'type': 'auth', 'access_token': self.token}))
            if json.loads(socket.recv()).get('type') != 'auth_ok':
                raise StatisticsError('History authentication rejected')
            sequence = 0

            def command(payload):
                nonlocal sequence
                sequence += 1
                socket.send(json.dumps(dict(payload, id=sequence), allow_nan=False))
                reply = json.loads(socket.recv())
                if reply.get('id') != sequence or not reply.get('success'):
                    raise StatisticsError('Home Assistant rejected statistics request')
                return reply.get('result')

            for batch in batches:
                command(dict(batch, type='recorder/import_statistics'))
            # Import acknowledgement only queues recorder work. Check persisted
            # sums, allowing time for the queue, before reporting success.
            expected = {b['metadata']['statistic_id']: b['stats'][-1]['sum'] for b in batches}
            last = batches[0]['stats'][-1]['start']
            end = (datetime.fromisoformat(last) + timedelta(hours=1)).isoformat()
            for attempt in range(5):
                result = command({'type': 'recorder/statistics_during_period', 'start_time': last,
                                  'end_time': end, 'statistic_ids': list(expected),
                                  'period': 'hour', 'types': ['sum']})
                if all(result.get(key) and abs(result[key][-1]['sum'] - value) < 0.000001
                       for key, value in expected.items()):
                    return 'ok'
                time.sleep(0.5 * (attempt + 1))
            raise StatisticsError('History persistence could not be confirmed')
        except StatisticsError:
            raise
        except Exception:
            raise StatisticsError('History connection or import failed') from None
        finally:
            if socket is not None:
                try:
                    socket.close()
                except Exception:
                    pass
