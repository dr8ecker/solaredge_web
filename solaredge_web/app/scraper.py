# Copyright (c) 2026 8ecker.de
"""Read quantities from rendered cards, SVG text and visible hover tooltips."""

import re
import unicodedata
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .discovery import KEYWORDS
from .models import DayEnergy, ScrapeResult
from .parser import ValueParser, ParseError
from .selectors import SELECTORS, unique

LOGGER = logging.getLogger(__name__)

# Discover a unique adjacent pair in the verified card scope. Color identifies
# rendered rectangles only; direction and quantity always come from a tooltip.
UNLABELLED_BAR_POSITIONS = r"""scope => {
  const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const all = Array.from(scope.querySelectorAll('*')).slice(0, 300);
  const labels = all.filter(el => visible(el) && /^\d+(?:[.,]\d+)?\s*%$/.test(el.innerText?.trim() || ''));
  const bounds = scope.getBoundingClientRect();
  const boxes = [], seen = new Set();
  for (const node of all) {
    if (!(node instanceof HTMLElement) || !visible(node) || node.closest('[role=tooltip]')) continue;
    const style = getComputedStyle(node), r = node.getBoundingClientRect();
    const gradient = /^(?:repeating-)?linear-gradient\(/.test(style.backgroundImage);
    const color = gradient ? style.backgroundImage : style.backgroundColor;
    if (style.opacity === '0' || (!gradient && (color === 'transparent' || color === 'rgba(0, 0, 0, 0)')) ||
        r.width < 2 || r.height < 8 || r.height > 48 || r.left < bounds.left - 1 ||
        r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1) continue;
    const signature = [r.x, r.y, r.width, r.height].map(x => x.toFixed(2)).join(',') + color;
    if (seen.has(signature)) continue;
    seen.add(signature);
    boxes.push({node, r, color, labelled: labels.some(label => node.contains(label))});
  }
  const pairs = [];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    if (a.color === b.color || (a.labelled && b.labelled) ||
        Math.abs(a.r.top - b.r.top) > 2 || Math.abs(a.r.height - b.r.height) > 2) continue;
    const [left, right] = a.r.left < b.r.left ? [a, b] : [b, a];
    const gap = right.r.left - left.r.right;
    if (gap < -1 || gap > 3) continue;
    pairs.push([a, b].filter(box => !box.labelled));
  }
  if (pairs.length !== 1) return [];
  const positions = [];
  for (const target of pairs[0]) {
    const x = target.r.left + target.r.width / 2, y = target.r.top + target.r.height / 2;
    const hit = document.elementFromPoint(x, y);
    if (!hit || !target.node.contains(hit)) return [];
    positions.push({x, y});
  }
  return positions;
}"""


class SolarEdgeScraper:
    def __init__(self, config):
        self.config = config

    @staticmethod
    def normalize_label(text):
        """Keep German/English words stable across visual typography variants."""
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[-\u2010-\u2015\u2212]', ' ', text)
        return ' '.join(text.split()).casefold()

    def energy_key(self, text, allowed):
        normalized = self.normalize_label(text)
        for name, words in (
            ('grid_export_energy', KEYWORDS['grid_export']),
            ('grid_import_energy', KEYWORDS['grid_import']),
            ('self_consumption_energy', KEYWORDS['pv_to_home']),
        ):
            if name in allowed and any(self.normalize_label(word) in normalized for word in words):
                return name
        return None

    async def unlabelled_bar_energy(self, page, card, card_name, allowed):
        await page.mouse.move(0, 0)
        await page.get_by_role('tooltip').wait_for(state='hidden', timeout=5000)
        positions = await card.evaluate(UNLABELLED_BAR_POSITIONS)
        parts, fields, unknown = {}, [], 0
        for index in range(len(positions)):
            await page.mouse.move(0, 0)
            await page.get_by_role('tooltip').wait_for(state='hidden', timeout=5000)
            current = await card.evaluate(UNLABELLED_BAR_POSITIONS)
            if len(current) != len(positions):
                continue
            position = current[index]
            prior = await page.locator('[role=tooltip]').all_text_contents()
            await page.mouse.move(position['x'], position['y'])
            try:
                await page.wait_for_function(r"""prior => Array.from(document.querySelectorAll('[role=tooltip]')).some(el => {
                  const text = el.innerText.trim();
                  return el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' &&
                    !prior.some(old => old.trim() === text) && /\d[.,\d\s]*\s*(?:kWh|MWh|Wh)(?!\/)/i.test(text);
                })""", arg=prior, timeout=5000)
            except PlaywrightTimeoutError:
                continue
            tooltip = page.get_by_role('tooltip')
            if await tooltip.count() != 1:
                raise ParseError('Tooltip is ambiguous', field=card_name)
            text = await tooltip.inner_text()
            key = self.energy_key(text, allowed)
            if key is None:
                unknown += 1
            else:
                fields.append(key)
                if key in parts:
                    raise ParseError('Tooltip is ambiguous', field=card_name)
                parts[key] = ValueParser.parse(text, 'kWh', field=key)
        return parts, len(positions), unknown, fields

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
        try:
            return await self._day_energy(page, expected)
        except ParseError as error:
            viewport = page.viewport_size
            if (error.reason not in {'distribution_energy_incomplete', 'distribution_labels_missing'}
                    or error.field not in {'production_card', 'consumption_card'}
                    or error.unrecognized_tooltip_count != 0
                    or not viewport or viewport['width'] >= 1920):
                raise
            # Responsive bars can omit percent text in small slices. Re-render
            # the same date once, then read real tooltips with all checks intact.
            LOGGER.warning('Energy distribution labels incomplete in %s; widening browser to 1920 px for one tooltip retry', error.field)
            await page.mouse.move(0, 0)
            await page.get_by_role('tooltip').wait_for(state='hidden', timeout=5000)
            await page.set_viewport_size({**viewport, 'width': 1920})
            await page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            await self.wait_energy(page)
            return await self._day_energy(page, expected)

    async def _day_energy(self, page, expected: date) -> DayEnergy:
        if await self.selected_dates(page) != (expected, expected):
            raise ValueError("Refusing overlapping or wrong energy period")
        quantities = {}
        production = await unique(page, 'production_card')
        consumption = await unique(page, 'consumption_card')
        quantities['pv_energy'] = ValueParser.parse(await production.inner_text(), 'kWh', field='production_card')
        quantities['consumption_energy'] = ValueParser.parse(await consumption.inner_text(), 'kWh', field='consumption_card')
        kpi = ValueParser.parse(await (await unique(page, 'kpis')).inner_text(), 'kWh', field='production_kpi')
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
        for card, card_name, allowed in ((production, 'production_card', {'grid_export_energy', 'self_consumption_energy'}),
                                         (consumption, 'consumption_card', {'grid_import_energy', 'self_consumption_energy'})):
            total = quantities['pv_energy' if card is production else 'consumption_energy']
            if total.value == 0:
                # A displayed zero total of nonnegative components proves zero.
                for key in allowed:
                    quantities.setdefault(key, total)
                continue
            labels = card.get_by_text(re.compile(r'^\d+(?:[.,]\d+)?\s*%$')).filter(visible=True)
            label_count = await labels.count()
            if label_count == 0:
                # Totals can render before their distribution. Briefly wait for
                # either actual labels or a unique rendered pair, then retry the
                # locator. An empty label list must still reach bar extraction.
                try:
                    await page.wait_for_function(r"""selector => {
                      const scope = document.querySelector(selector);
                      if (!scope) return false;
                      const labels = Array.from(scope.querySelectorAll('*')).some(el =>
                        el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' &&
                        /^\d+(?:[.,]\d+)?\s*%$/.test(el.innerText?.trim() || ''));
                      return labels || (BAR_POSITIONS)(scope).length > 0;
                    }""".replace('BAR_POSITIONS', UNLABELLED_BAR_POSITIONS),
                        arg=SELECTORS[card_name][0], timeout=1500)
                except PlaywrightTimeoutError:
                    pass
                label_count = await labels.count()
            parts = {}
            unrecognized_tooltip_count = 0
            for label in await labels.all():
                # Dismiss the previous tooltip even when both portions say 50%.
                await page.mouse.move(0, 0)
                await page.get_by_role('tooltip').wait_for(state='hidden', timeout=5000)
                percent = (await label.inner_text()).strip()
                await label.hover()
                await page.wait_for_function("percent => Array.from(document.querySelectorAll('[role=tooltip]')).some(el => el.getClientRects().length && el.innerText.trim().startsWith(percent + ' '))", arg=percent, timeout=5000)
                tooltip = page.get_by_role('tooltip')
                if await tooltip.count() != 1:
                    raise ParseError("Tooltip is ambiguous", field=card_name)
                text = await tooltip.inner_text()
                key = self.energy_key(text, allowed)
                if key:
                    parts[key] = ValueParser.parse(text, 'kWh', field=key)
                else:
                    unrecognized_tooltip_count += 1
            # Self-use is the same energy in both cards. Reuse the explicit
            # production quantity, including its resolution, if the second
            # label is absent. Unknown tooltips remain errors. Require an import
            # and a matching consumption total; never derive it from percent.
            for key in allowed - parts.keys():
                if key == 'self_consumption_energy' and key in quantities and not unrecognized_tooltip_count:
                    parts[key] = quantities[key]
            bar_candidate_count, bar_fields = None, []
            if not allowed <= parts.keys() and not unrecognized_tooltip_count:
                bar_parts, bar_candidate_count, bar_unknown, bar_fields = await self.unlabelled_bar_energy(
                    page, card, card_name, allowed)
                parts.update(bar_parts)
                unrecognized_tooltip_count += bar_unknown
                if bar_parts:
                    LOGGER.info('Energy tooltip read from an unlabelled bar in %s: %s', card_name, ', '.join(sorted(bar_parts)))
            if not allowed <= parts.keys():
                message = "Distribution labels missing; no zero assumed" if label_count == 0 else "Distribution energy incomplete; run discovery"
                raise ParseError(message, field=card_name,
                                 missing_fields=allowed - parts.keys(), label_count=label_count,
                                 unrecognized_tooltip_count=unrecognized_tooltip_count,
                                 bar_hover_candidate_count=bar_candidate_count, bar_tooltip_fields=bar_fields)
            difference = abs(sum(q.value for q in parts.values()) - total.value)
            tolerance = total.resolution + sum(q.resolution for q in parts.values())
            if difference > tolerance:
                raise ParseError("Distribution does not match displayed total", field=card_name)
            for key, quantity in parts.items():
                if key in quantities and abs(quantities[key].value - quantity.value) > max(quantities[key].resolution, quantity.resolution):
                    raise ParseError("Production and consumption self-use disagree", field=key)
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
