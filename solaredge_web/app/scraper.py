# Copyright (c) 2026 8ecker.de
"""Read quantities from rendered cards, SVG text and visible hover tooltips."""

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .discovery import KEYWORDS
from .models import DayEnergy, ScrapeResult
from .parser import ValueParser, ParseError
from .selectors import unique


class SolarEdgeScraper:
    def __init__(self, config):
        self.config = config

    @staticmethod
    def grid_power(text):
        """A single positive, labelled net flow establishes zero opposite flow."""
        groups = []
        for direction in ('grid_import', 'grid_export'):
            words = '|'.join(re.escape(word) for word in sorted(KEYWORDS[direction], key=len, reverse=True))
            groups.append(f'(?P<{direction}>{words})')
        labels = list(re.finditer(r'(?<!\w)(?:' + '|'.join(groups) + r')(?!\w)', text, re.I))
        values = {}
        for label in labels:
            key = label.lastgroup + '_power'
            quantity = ValueParser.PATTERN.match(text[label.end():].lstrip())
            if key in values or quantity is None:
                raise ParseError('Grid direction ambiguous or missing a quantity')
            values[key] = float(ValueParser.parse(quantity.group(), 'W').value)
        if len(values) == 1 and next(iter(values.values())) > 0:
            opposite = ({'grid_import_power', 'grid_export_power'} - values.keys()).pop()
            values[opposite] = 0.0
        return values

    async def begin_transition(self, page):
        # Observe the actual energy scopes, not URL requests or chart internals.
        await page.evaluate("""() => {
          window.__seObserver?.disconnect();
          window.__seEnergyChange = {seen:false, last:performance.now()};
          window.__seObserver = new MutationObserver(() => {
            window.__seEnergyChange.seen = true;
            window.__seEnergyChange.last = performance.now();
          });
          for(const scope of ['#dashboard-kpis','[data-testid="power-energy-chart-component"]']) {
            const node = document.querySelector(scope);
            if(node) window.__seObserver.observe(node, {childList:true, subtree:true, characterData:true});
          }
        }""")

    async def wait_energy(self, page, *, changed=False):
        await page.wait_for_function("""changed => {
          const visible = el => el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
          const scopes = ['#dashboard-kpis','#distribution-component-produktion','#distribution-component-verbrauch'];
          const ready = scopes.every(s => {
            const el = document.querySelector(s);
            return visible(el) && /[0-9][.,0-9\\s]*\\s*(?:kWh|MWh|Wh)(?!\\/)/i.test(el.innerText);
          });
          const progress = Array.from(document.querySelectorAll('[role=progressbar],[aria-busy=true]')).some(visible);
          const transition = window.__seEnergyChange;
          return ready && !progress && (!changed || (transition?.seen && performance.now() - transition.last > 1000));
        }""", arg=changed, timeout=self.config.page_timeout)

    async def select_today(self, page):
        picker = await unique(page, 'date_picker')
        combo = picker.get_by_role('combobox')
        current = (await combo.inner_text()).strip()
        before_dates = await self.selected_dates(page)
        local_today = datetime.now(ZoneInfo(self.config.site_timezone)).date()
        changed = current not in {'Tag', 'Day'} or before_dates != (local_today, local_today)
        await self.begin_transition(page)
        await (await unique(page, 'today')).click()
        chart = await unique(page, 'chart')
        energy = chart.get_by_role('button', name=re.compile(r'^(Energie|Energy)$'))
        await energy.click()
        await self.wait_energy(page, changed=changed)
        dates = await self.selected_dates(page)
        if dates[0] != dates[1]:
            raise ValueError("Today did not select a single calendar day")
        return dates[0]

    async def selected_dates(self, page):
        raw = await (await unique(page, 'date_input')).input_value()
        tokens = re.findall(r'\d{2}\.\d{2}\.\d{4}', raw)
        if len(tokens) != 2:
            raise ValueError("Unrecognized UI date format; run discovery")
        return tuple(datetime.strptime(t, '%d.%m.%Y').date() for t in tokens)

    async def previous_day(self, page, expected: date):
        await self.begin_transition(page)
        await (await unique(page, 'previous')).click()
        await page.wait_for_function("""expected => document.querySelector('[data-testid="dashboard-date-range-input"]')?.value === expected""", arg=f'{expected:%d.%m.%Y} – {expected:%d.%m.%Y}')
        await self.wait_energy(page, changed=True)
        if await self.selected_dates(page) != (expected, expected):
            raise ValueError("Historical period did not match requested day")

    async def day_energy(self, page, expected: date) -> DayEnergy:
        if await self.selected_dates(page) != (expected, expected):
            raise ValueError("Refusing overlapping or wrong energy period")
        quantities = {}
        production = await unique(page, 'production_card')
        consumption = await unique(page, 'consumption_card')
        quantities['pv_energy'] = ValueParser.parse(await production.inner_text(), 'kWh')
        quantities['consumption_energy'] = ValueParser.parse(await consumption.inner_text(), 'kWh')
        kpi = ValueParser.parse(await (await unique(page, 'kpis')).inner_text(), 'kWh')
        if abs(kpi.value - quantities['pv_energy'].value) > max(kpi.resolution, quantities['pv_energy'].resolution):
            raise ValueError("Energy cards and production KPI disagree; page still loading")
        # Zero totals can establish a component even when its percentage label
        # is omitted. A rounded 100% label alone never proves a zero component.
        if quantities['pv_energy'].value == 0:
            quantities['grid_export_energy'] = quantities['pv_energy']
            quantities['self_consumption_energy'] = quantities['pv_energy']
        if quantities['consumption_energy'].value == 0:
            quantities['grid_import_energy'] = quantities['consumption_energy']
            quantities['self_consumption_energy'] = quantities['consumption_energy']
        for card, allowed in ((production, {'grid_export_energy', 'self_consumption_energy'}),
                              (consumption, {'grid_import_energy', 'self_consumption_energy'})):
            total = quantities['pv_energy' if card is production else 'consumption_energy']
            if total.value == 0:
                # A displayed zero total of nonnegative components proves zero.
                for key in allowed:
                    quantities.setdefault(key, total)
                continue
            labels = card.get_by_text(re.compile(r'^\d+(?:[.,]\d+)?\s*%$'))
            if await labels.count() == 0:
                raise ParseError("Distribution labels missing; no zero assumed")
            parts = {}
            for label in await labels.all():
                # Dismiss the previous tooltip even when both portions say 50%.
                await page.mouse.move(0, 0)
                await page.get_by_role('tooltip').wait_for(state='hidden', timeout=5000)
                percent = (await label.inner_text()).strip()
                await label.hover()
                await page.wait_for_function("percent => Array.from(document.querySelectorAll('[role=tooltip]')).some(el => el.getClientRects().length && el.innerText.trim().startsWith(percent + ' '))", arg=percent, timeout=5000)
                tooltip = page.get_by_role('tooltip')
                if await tooltip.count() != 1:
                    raise ParseError("Tooltip is ambiguous")
                text = await tooltip.inner_text()
                key = None
                for name, words in (
                    ('grid_export_energy', KEYWORDS['grid_export']),
                    ('grid_import_energy', KEYWORDS['grid_import']),
                    ('self_consumption_energy', KEYWORDS['pv_to_home']),
                ):
                    if name in allowed and any(word.lower() in text.lower() for word in words):
                        key = name
                        break
                if key:
                    parts[key] = ValueParser.parse(text, 'kWh')
            # Do not fill in an absent portion from rounded percentages.
            for key in allowed - parts.keys():
                if key == 'self_consumption_energy' and key in quantities and quantities[key].value == 0:
                    parts[key] = quantities[key]
            if not allowed <= parts.keys():
                raise ParseError("Distribution energy incomplete; run discovery")
            difference = abs(sum(q.value for q in parts.values()) - total.value)
            tolerance = total.resolution + sum(q.resolution for q in parts.values())
            if difference > tolerance:
                raise ParseError("Distribution does not match displayed total")
            for key, quantity in parts.items():
                if key in quantities and abs(quantities[key].value - quantity.value) > max(quantities[key].resolution, quantity.resolution):
                    raise ParseError("Production and consumption self-use disagree")
                quantities[key] = quantity
        await page.mouse.move(0, 0)
        if await self.selected_dates(page) != (expected, expected):
            raise ValueError("Date changed during scrape")
        return DayEnergy(expected, {k:q.value for k,q in quantities.items()}, {k:q.resolution for k,q in quantities.items()})

    async def live(self, page) -> ScrapeResult:
        result = ScrapeResult(values={'scraped_at': datetime.now(timezone.utc).isoformat()})
        for key, scope, unit in (('outside_temperature', 'temperature', '°C'), ('pv_power', 'pv_power', 'W')):
            try:
                target = await unique(page, scope)
                text = await target.inner_text()
                if key == 'pv_power':
                    nominal = target.locator('[data-testid="current-power.nomalized-max-power"]')
                    if await nominal.count() == 1:
                        text = text.replace(await nominal.inner_text(), '')
                result.values[key] = float(ValueParser.parse(text, unit).value)
            except Exception:
                result.warnings.append(key)
        try:
            status = (await (await unique(page, 'site_status')).inner_text()).strip().lower()
            result.values['site_status'] = status
        except Exception:
            result.warnings.append('site_status')
        try:
            label = page.get_by_text(re.compile(r'^(Aktualisiert:|Updated:)$'))
            if await label.count() == 1:
                text = await label.evaluate('el => el.parentElement.innerText')
                result.values['last_update'] = text.split(':', 1)[-1].strip()[:100]
        except Exception:
            result.warnings.append('last_update')
        try:
            flow = await unique(page, 'flow')
            text = await flow.evaluate("""el => Array.from(el.querySelectorAll('svg text'))
                .filter(x => x.getClientRects().length && getComputedStyle(x).visibility !== 'hidden')
                .map(x => x.textContent).join(' ')""")
            for key, words in (('consumption_power', KEYWORDS['consumption']),):
                pattern = '|'.join(re.escape(w) for w in sorted(words, key=len, reverse=True))
                match = re.search(r'(?:' + pattern + r')\s*([-+]?\d[\d.,\s]*\s*(?:kW|MW|W))', text, re.I)
                if match:
                    result.values[key] = float(ValueParser.parse(match.group(1), 'W').value)
            result.values.update(self.grid_power(text))
        except Exception:
            result.warnings.append('power_flow')
        return result
