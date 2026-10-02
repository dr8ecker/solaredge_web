"""Persisted per-day high-water ledger; no overlapping ranges or reset zeros."""

import copy
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from .files import write_private_json

ENERGY_KEYS = ('pv_energy', 'grid_import_energy', 'grid_export_energy', 'consumption_energy', 'self_consumption_energy')


class LedgerError(RuntimeError):
    pass


def identity(config):
    # Stable across reinstalls; the username is never transmitted in clear text.
    return hashlib.sha256((config.monitoring_url + '\0' + config.solar_edge_username.lower() + '\0' + config.plant_name).encode()).hexdigest()[:20]


class EnergyLedger:
    def __init__(self, config):
        self.config = config
        self.path = config.data_dir / 'energy_ledger.json'
        self.backup = config.data_dir / 'energy_ledger.backup.json'
        self.marker = config.data_dir / 'energy_initialized.json'
        self.state = {'version':1, 'identity':identity(config), 'days':{},
                      'carry':{k:'0' for k in ENERGY_KEYS}, 'last_day':None, 'gaps':[]}
        if self.path.exists():
            try:
                self.state = self.validate(json.loads(self.path.read_text(encoding='utf8')))
            except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
                # A backup is diagnostic only: silently restoring an older total
                # would produce a negative statistic. Stop until repaired.
                raise LedgerError('Energy ledger damaged; preserve data and restore a consistent backup') from None
        elif self.marker.exists() or self.backup.exists():
            raise LedgerError('Energy ledger missing after initialization; refusing a reset to zero')

    def validate(self, state):
        if state['version'] != 1 or state['identity'] != identity(self.config):
            raise LedgerError('Energy ledger belongs to another configured plant/account')
        if state['last_day']:
            date.fromisoformat(state['last_day'])
        for key in ENERGY_KEYS:
            value = Decimal(state['carry'][key])
            if not value.is_finite() or value < 0:
                raise ValueError('Invalid carry')
        for day, values in state['days'].items():
            date.fromisoformat(day)
            if set(values) != set(ENERGY_KEYS):
                raise ValueError('Incomplete ledger')
            for value in values.values():
                number = Decimal(value)
                if not number.is_finite() or number < 0:
                    raise ValueError('Invalid daily quantity')
        return state

    def needed_days(self, today):
        if not self.state['last_day']:
            return []
        last = date.fromisoformat(self.state['last_day'])
        if today < last:
            raise LedgerError('UI date moved backwards; check site_timezone')
        # Re-read yesterday to catch a late final meter upload/correction.
        start = max(last, today - timedelta(days=self.config.history_days))
        if today == last:
            yesterday = today - timedelta(days=1)
            return [yesterday] if yesterday.isoformat() in self.state['days'] else []
        return [start + timedelta(days=i) for i in range((today-start).days)]

    def apply(self, samples):
        if not samples:
            raise LedgerError('No energy samples')
        new = copy.deepcopy(self.state)
        warnings = []
        today = max(s.day for s in samples)
        previous = date.fromisoformat(new['last_day']) if new['last_day'] else None
        available = {s.day for s in samples}
        if previous and today > previous:
            for i in range((today-previous).days):
                day = previous + timedelta(days=i)
                if day not in available:
                    if day.isoformat() not in new['gaps']:
                        new['gaps'].append(day.isoformat())
        for sample in samples:
            if set(sample.values) != set(ENERGY_KEYS):
                raise LedgerError('Incomplete daily energy sample')
            old = new['days'].get(sample.day.isoformat(), {})
            row = {}
            for key in ENERGY_KEYS:
                value = sample.values[key]
                if not value.is_finite() or value < 0:
                    raise LedgerError('Invalid energy quantity')
                previous_value = Decimal(old.get(key, '0'))
                if value < previous_value:
                    warnings.append(key + ': displayed daily energy decreased; previous maximum retained')
                row[key] = str(max(value, previous_value))
            new['days'][sample.day.isoformat()] = row
            if sample.day.isoformat() in new['gaps']:
                new['gaps'].remove(sample.day.isoformat())
        new['last_day'] = today.isoformat()
        # Compact only old completed days, retaining the bounded correction window.
        boundary = today - timedelta(days=max(32, self.config.history_days + 1))
        for day in list(new['days']):
            if date.fromisoformat(day) < boundary:
                for key in ENERGY_KEYS:
                    new['carry'][key] = str(Decimal(new['carry'][key]) + Decimal(new['days'][day][key]))
                del new['days'][day]
        # Commit before MQTT: retrying a publication can never double count.
        if self.path.exists():
            write_private_json(self.backup, self.state)
        write_private_json(self.path, new)
        write_private_json(self.marker, {'identity':identity(self.config), 'version':1})
        self.state = new
        return {key + '_total':float(Decimal(new['carry'][key]) + sum(Decimal(row[key]) for row in new['days'].values())) for key in ENERGY_KEYS}, warnings
