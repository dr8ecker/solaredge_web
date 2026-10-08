# Copyright (c) 2026 8ecker.de
"""Synthetic DOM fixtures reproduce discovered scopes, including async loading."""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.browser import BrowserManager
from app.config import Config
from app.scraper import SolarEdgeScraper
from app.parser import ParseError
from app.diagnostics import failure_details


class ScraperBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(data_dir=Path(self.directory.name),page_timeout=5000)
        self.browser = BrowserManager(self.config)
        await self.browser.start()
        self.scraper = SolarEdgeScraper(self.config)
        self.day = datetime.now(ZoneInfo(self.config.site_timezone)).date()
        self.date_text = f'{self.day:%d.%m.%Y} – {self.day:%d.%m.%Y}'

    async def asyncTearDown(self):
        await self.browser.close()

    async def fixture(self, production='10', consumption='10'):
        await self.browser.page.set_content(f'''<html><body>
          <div id="se-date-range-picker"><div role="combobox">Tag</div>
          <input data-testid="dashboard-date-range-input" value="{self.date_text}">
          <button data-testid="today-button">Heute</button></div>
          <div id="dashboard-kpis">Produzierte Energie <span>{production} kWh</span> Bestimmter Ertrag 2 Wh/Wp</div>
          <div data-testid="power-energy-chart-component">
          <button>Energie</button>
          <div id="distribution-component-produktion">Produktion {production} kWh
          <span data-tip="Ins Netz: 5 kWh">50%</span><span data-tip="Ins Gebäude: 5 kWh">50%</span></div>
          <div id="distribution-component-verbrauch">Verbrauch {consumption} kWh
          <span data-tip="Vom Netz: 5 kWh">50%</span><span data-tip="Aus PV-Energie: 5 kWh">50%</span></div></div>
          <div data-testid="current-power-component">Live-PV-Erzeugung 2.4 kW
          <div data-testid="current-power.nomalized-max-power">16 kW AC-Nennwert</div></div>
          <div data-testid="power-flow-live-image"><svg><text>Importiert</text><text>0.81kW</text><text>Last</text><text>0.81kW</text></svg></div>
          <div id="site-connectivity-status-ONLINE">Online</div>
          <span data-testid="weather-widget.live-temperature">17˚C</span>
          <div><span>Aktualisiert:</span> 1 Minute vor</div>
          <div role="tooltip" style="display:none"></div>
          <script>
          for(const el of document.querySelectorAll('[data-tip]')) {{
           el.onmouseenter=()=>{{const t=document.querySelector('[role=tooltip]'); t.textContent=el.textContent+' '+el.dataset.tip;t.style.display='block';}};
           el.onmouseleave=()=>{{document.querySelector('[role=tooltip]').style.display='none';}};
          }}
          </script></body></html>''')

    async def test_equal_percentage_tooltips_do_not_reuse_stale_text(self):
        await self.fixture()
        sample = await self.scraper.day_energy(self.browser.page,self.day)
        self.assertEqual(sample.values['grid_import_energy'],5)
        self.assertEqual(sample.values['grid_export_energy'],5)
        self.assertEqual(sample.values['self_consumption_energy'],5)

    async def test_from_solar_consumption_label_reads_explicit_energy(self):
        # English wording observed in the user's screenshot; quantities are
        # synthetic tooltip values, not inferred from the rounded percentages.
        await self.fixture()
        await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('el=>el.dataset.tip="From Solar: 5 kWh"')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['self_consumption_energy'], 5)
        self.assertEqual(sample.values['grid_import_energy'], 5)

    async def test_english_distribution_labels_read_all_energy_fields(self):
        await self.fixture()
        await self.browser.page.evaluate('''() => {
          const translations = {'Ins Netz': 'To Grid', 'Ins Gebäude': 'To Building',
                                'Vom Netz': 'From Grid', 'Aus PV-Energie': 'From Solar'};
          for (const el of document.querySelectorAll('[data-tip]')) {
            for (const [original, translated] of Object.entries(translations)) {
              el.dataset.tip = el.dataset.tip.replace(original, translated);
            }
          }
          document.querySelector('[role=combobox]').textContent = 'Day';
          document.querySelector('[data-testid=today-button]').textContent = 'Today';
          document.querySelector('[data-testid=power-energy-chart-component] button').textContent = 'Energy';
        }''')
        self.assertEqual(await self.scraper.select_today(self.browser.page), self.day)
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values, {'pv_energy': 10, 'consumption_energy': 10,
                                       'grid_export_energy': 5, 'grid_import_energy': 5,
                                       'self_consumption_energy': 5})

    async def test_german_tooltips_and_rounded_totals_from_screenshots(self):
        # This reproduces visible values and wording, not the private live DOM.
        await self.fixture(production='46', consumption='7.34')
        await self.browser.page.evaluate('''() => {
          const tips = [
            ['#distribution-component-produktion', [['89%', 'Ins Netz: 41.1 kWh'], ['11%', 'Ins Gebäude: 4.85 kWh']]],
            ['#distribution-component-verbrauch', [['34%', 'Vom Netz: 2.5 kWh'], ['66%', 'Aus PV-Energie: 4.85 kWh']]],
          ];
          for (const [scope, values] of tips) {
            document.querySelectorAll(scope + ' [data-tip]').forEach((el, i) => {
              el.textContent = values[i][0]; el.dataset.tip = values[i][1];
            });
          }
        }''')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual({key: str(value) for key, value in sample.values.items()},
                         {'pv_energy': '46', 'consumption_energy': '7.34',
                          'grid_export_energy': '41.1', 'grid_import_energy': '2.5',
                          'self_consumption_energy': '4.85'})

    async def test_narrow_layout_hides_import_label_but_wider_layout_reads_its_tooltip(self):
        await self.fixture()
        await self.browser.page.set_viewport_size({'width': 1440, 'height': 1000})
        await self.browser.page.evaluate('''() => {
          const label = document.querySelector('[data-tip="Vom Netz: 5 kWh"]');
          const render = () => label.textContent = innerWidth >= 1700 ? '50%' : '';
          addEventListener('resize', render); render();
        }''')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['grid_import_energy'], 5)
        self.assertEqual(sample.values['self_consumption_energy'], 5)
        self.assertEqual(self.browser.page.viewport_size['width'], 1920)

    async def unlabelled_import_bar(self, *, tooltip='Vom Netz: 2.6 kWh', show_tooltip=True):
        await self.fixture(production='58.7', consumption='6.5')
        await self.browser.page.evaluate('''({tip, show}) => {
          const production = document.querySelectorAll('#distribution-component-produktion [data-tip]');
          production[0].textContent='93%'; production[0].dataset.tip='Ins Netz: 54.8 kWh';
          production[1].textContent='7%'; production[1].dataset.tip='Ins Gebäude: 3.9 kWh';
          const card = document.querySelector('#distribution-component-verbrauch');
          const portions = Array.from(card.querySelectorAll('[data-tip]'));
          const bar = document.createElement('div');
          bar.style.cssText='display:flex;width:90px;height:28px';
          portions[0].textContent=''; portions[0].dataset.tip=tip;
          portions[0].style.cssText='display:block;width:36px;height:28px;background-color:rgb(255, 170, 80)';
          portions[1].textContent='60%'; portions[1].dataset.tip='Aus PV-Energie: 3.9 kWh';
          portions[1].style.cssText='display:block;width:54px;height:28px;background-color:rgb(130, 175, 250)';
          portions.forEach(el => bar.append(el)); card.append(bar);
          portions[0].onmouseenter=()=>{
            if (!show) return;
            const t=document.querySelector('[role=tooltip]');
            t.textContent='40% '+tip; t.style.display='block';
          };
        }''', {'tip': tooltip, 'show': show_tooltip})

    async def test_import_tooltip_is_read_from_unlabelled_bar_even_at_1920_pixels(self):
        await self.unlabelled_import_bar()
        await self.browser.page.set_viewport_size({'width': 1920, 'height': 1000})
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(str(sample.values['grid_import_energy']), '2.6')
        self.assertEqual(str(sample.values['self_consumption_energy']), '3.9')
        self.assertEqual(str(sample.values['consumption_energy']), '6.5')

    async def all_bars_without_labels(self, *, language='de'):
        await self.fixture()
        await self.browser.page.evaluate('''language => {
          const definitions = language === 'de' ? [
            ['#distribution-component-produktion', ['Ins Netz: 5 kWh', 'Ins Gebäude: 5 kWh']],
            ['#distribution-component-verbrauch', ['Vom Netz: 5 kWh', 'Aus PV-Energie: 5 kWh']]
          ] : [
            ['#distribution-component-produktion', ['To Grid: 5 kWh', 'To Building: 5 kWh']],
            ['#distribution-component-verbrauch', ['From Grid: 5 kWh', 'From Solar: 5 kWh']]
          ];
          for (const [selector, tips] of definitions) {
            const card=document.querySelector(selector), bar=document.createElement('div');
            bar.style.cssText='display:flex;width:80px;height:28px';
            Array.from(card.querySelectorAll('[data-tip]')).forEach((portion,i)=>{
              portion.textContent=''; portion.dataset.tip=tips[i];
              portion.style.cssText='display:block;width:40px;height:28px;background-color:'+(i===0?'rgb(255, 170, 80)':'rgb(130, 175, 250)');
              portion.onmouseenter=()=>{const t=document.querySelector('[role=tooltip]');t.textContent=(i===0?'40% ':'60% ')+portion.dataset.tip;t.style.display='block';};
              bar.append(portion);
            });
            card.append(bar);
          }
        }''', language)

    async def test_production_and_consumption_without_any_percent_labels_read_both_tooltips(self):
        for language in ('de', 'en'):
            with self.subTest(language=language):
                await self.all_bars_without_labels(language=language)
                sample = await self.scraper.day_energy(self.browser.page, self.day)
                self.assertEqual(sample.values, {'pv_energy': 10, 'consumption_energy': 10,
                                               'grid_export_energy': 5, 'grid_import_energy': 5,
                                               'self_consumption_energy': 5})

    async def test_unlabelled_gradient_bars_read_explicit_tooltips(self):
        await self.all_bars_without_labels()
        await self.browser.page.locator('[data-tip]').evaluate_all('''els=>els.forEach((el,i)=>{
          el.style.background=i%2===0?'linear-gradient(to right, rgb(40, 190, 200), rgb(110, 220, 220))':'linear-gradient(to right, rgb(50, 210, 140), rgb(100, 240, 180))';
        })''')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['grid_export_energy'], 5)
        self.assertEqual(sample.values['grid_import_energy'], 5)

    async def test_duplicate_directions_on_two_unlabelled_segments_are_rejected(self):
        await self.all_bars_without_labels()
        await self.browser.page.locator('#distribution-component-verbrauch [data-tip]').evaluate_all('els=>els.forEach(el=>el.dataset.tip="Vom Netz: 5 kWh")')
        with self.assertRaises(ParseError):
            await self.scraper.day_energy(self.browser.page, self.day)

    async def test_newly_rendered_percent_labels_are_awaited_before_failure(self):
        await self.fixture()
        await self.browser.page.evaluate('''() => {
          const labels=Array.from(document.querySelectorAll('#distribution-component-produktion [data-tip]'));
          labels.forEach(el=>el.textContent='');
          setTimeout(()=>labels.forEach(el=>el.textContent='50%'), 300);
        }''')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['grid_export_energy'], 5)
        self.assertEqual(sample.values['self_consumption_energy'], 5)

    async def test_unlabelled_consumption_self_use_is_checked_against_production(self):
        await self.all_bars_without_labels()
        await self.browser.page.locator('#distribution-component-verbrauch [data-tip]').last.evaluate('el=>el.dataset.tip="Aus PV-Energie: 15 kWh"')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(caught.exception.reason, 'distribution_total_mismatch')

    async def test_unknown_unlabelled_bar_tooltip_never_supplies_import(self):
        await self.unlabelled_import_bar(tooltip='Unrecognized component: 2.6 kWh')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        details = failure_details(caught.exception)
        self.assertEqual(details['missing_fields'], ['grid_import_energy'])
        self.assertEqual(details['bar_hover_candidate_count'], 1)
        self.assertEqual(details['unrecognized_tooltip_count'], 1)

    async def test_missing_bar_tooltip_never_reuses_the_previous_pv_tooltip(self):
        await self.unlabelled_import_bar(show_tooltip=False)
        await self.browser.page.set_viewport_size({'width': 1920, 'height': 1000})
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        details = failure_details(caught.exception)
        self.assertEqual(details['missing_fields'], ['grid_import_energy'])
        self.assertEqual(details['bar_hover_candidate_count'], 1)
        self.assertEqual(details['bar_tooltip_fields'], [])

    async def test_unlabelled_bar_with_mismatched_import_is_rejected(self):
        await self.unlabelled_import_bar(tooltip='Vom Netz: 20 kWh')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(caught.exception.reason, 'distribution_total_mismatch')

    async def test_multiple_unlabelled_bar_pairs_are_not_guessed(self):
        await self.unlabelled_import_bar()
        await self.browser.page.set_viewport_size({'width': 1920, 'height': 1000})
        await self.browser.page.locator('#distribution-component-verbrauch > div').evaluate('''el => {
          const copy=el.cloneNode(true);
          for (const portion of copy.querySelectorAll('[data-tip]')) {
            portion.onmouseenter=()=>{const t=document.querySelector('[role=tooltip]');t.textContent=portion.textContent+' '+portion.dataset.tip;t.style.display='block';};
            portion.onmouseleave=()=>document.querySelector('[role=tooltip]').style.display='none';
          }
          el.parentElement.append(copy);
        }''')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        details = failure_details(caught.exception)
        self.assertEqual(details['missing_fields'], ['grid_import_energy'])
        self.assertEqual(details['bar_hover_candidate_count'], 0)

    async def test_wider_layout_never_invents_a_still_missing_import(self):
        await self.fixture()
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el => el.remove()')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(failure_details(caught.exception)['missing_fields'], ['grid_import_energy'])
        self.assertEqual(self.browser.page.viewport_size['width'], 1920)

    async def test_css_hidden_import_label_is_read_after_responsive_resize(self):
        await self.fixture()
        await self.browser.page.add_style_tag(content='@media (max-width: 1700px) { [data-tip="Vom Netz: 5 kWh"] { display: none; } }')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['grid_import_energy'], 5)
        self.assertEqual(self.browser.page.viewport_size['width'], 1920)

    async def test_unknown_import_label_is_reported_without_resizing(self):
        await self.fixture()
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el => el.dataset.tip="Unrecognized component: 5 kWh"')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        details = failure_details(caught.exception)
        self.assertEqual(details['missing_fields'], ['grid_import_energy'])
        self.assertEqual(details['distribution_label_count'], 2)
        self.assertEqual(details['unrecognized_tooltip_count'], 1)
        self.assertEqual(self.browser.page.viewport_size['width'], 1440)

    async def test_consumption_reuses_explicit_production_self_use_when_pv_label_is_absent(self):
        await self.fixture()
        await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('el => el.remove()')
        sample = await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(sample.values['self_consumption_energy'], 5)
        self.assertEqual(sample.values['grid_import_energy'], 5)
        self.assertEqual(str(sample.resolutions['self_consumption_energy']), '1')

    async def test_shared_self_use_never_accepts_a_mismatched_consumption_total(self):
        await self.fixture(consumption='20')
        await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('el => el.remove()')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(caught.exception.reason, 'distribution_total_mismatch')

    async def test_unrecognized_pv_tooltip_remains_an_error(self):
        await self.fixture()
        await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('el => el.dataset.tip="Unrecognized component: 5 kWh"')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(caught.exception.reason, 'distribution_energy_incomplete')
        self.assertEqual(failure_details(caught.exception)['missing_fields'], ['self_consumption_energy'])

    async def test_german_and_english_labels_accept_typographic_spaces_and_hyphens(self):
        # A conflicting quantity must still be read and rejected. This proves
        # matching works rather than silently using the production fallback.
        for text in ('Aus\u00a0PV\u2011Energie', 'Aus PV\u2013Energie',
                     'From\u202fSolar', 'PV\u2010Energy'):
            with self.subTest(text=text):
                await self.fixture()
                await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('(el, tip) => el.dataset.tip=tip', text + ': 15 kWh')
                with self.assertRaises(ParseError) as caught:
                    await self.scraper.day_energy(self.browser.page, self.day)
                self.assertEqual(caught.exception.reason, 'distribution_total_mismatch')

    async def test_nominal_rating_is_not_the_pv_measurement(self):
        await self.fixture()
        result = await self.scraper.live(self.browser.page)
        self.assertEqual(result.values['pv_power'],2400)
        self.assertEqual(result.values['grid_import_power'],810)
        self.assertEqual(result.values['grid_export_power'],0)

    async def test_confirmed_flow_switches_the_opposite_direction_to_zero(self):
        await self.fixture()
        flow = self.browser.page.get_by_test_id('power-flow-live-image')
        for label, value, direction, expected in (
            ('Exportieren', '9.6kW', 'grid_export_power', 9600),
            ('Importiert', '730 W', 'grid_import_power', 730),
            ('To Grid', '2,4 kW', 'grid_export_power', 2400),
            ('From Grid', '0.5 kW', 'grid_import_power', 500),
            ('Exporting', '2.7 kW', 'grid_export_power', 2700),
            ('Importing', '730 W', 'grid_import_power', 730),
        ):
            with self.subTest(label=label):
                await flow.evaluate('(el, text) => el.querySelector("svg").innerHTML = text', f'<text>{label}</text><text>{value}</text><text>Last</text><text>730 W</text>')
                result = await self.scraper.live(self.browser.page)
                self.assertEqual(result.values[direction],expected)
                opposite = ({'grid_import_power', 'grid_export_power'} - {direction}).pop()
                self.assertEqual(result.values[opposite],0)
                self.assertEqual(result.values['consumption_power'],730)

    async def test_unknown_invalid_or_ambiguous_flows_never_invent_zero(self):
        await self.fixture()
        flow = self.browser.page.get_by_test_id('power-flow-live-image')
        for text in (
            'Netz 9.6kW Last 730 W',
            'Exportieren Loading Last 730 W',
            'Exportieren -9.6kW Last 730 W',
            'Exportieren 9.6kWh Last 730 W',
            'Exportieren 9.6kW Importiert Loading Last 730 W',
            'Exportieren 9.6kW Exportieren 8kW Last 730 W',
            'UnbekannterExport 9.6kW Last 730 W',
        ):
            with self.subTest(text=text):
                await flow.evaluate('(el, text) => el.querySelector("svg text").textContent = text', text)
                await flow.locator('svg text').evaluate_all('els => els.slice(1).forEach(el => el.remove())')
                result = await self.scraper.live(self.browser.page)
                self.assertNotIn('grid_import_power',result.values)
                self.assertNotIn('grid_export_power',result.values)

    async def test_zero_flow_does_not_establish_an_unlabelled_direction(self):
        await self.fixture()
        await self.browser.page.get_by_test_id('power-flow-live-image').evaluate('el => el.querySelector("svg").innerHTML = "<text>Exportieren 0 W Last 730 W</text>"')
        result = await self.scraper.live(self.browser.page)
        self.assertEqual(result.values['grid_export_power'],0)
        self.assertNotIn('grid_import_power',result.values)

    async def test_hidden_opposite_flow_is_ignored_and_explicit_values_are_preserved(self):
        await self.fixture()
        flow = self.browser.page.get_by_test_id('power-flow-live-image')
        await flow.evaluate('(el, html) => el.querySelector("svg").innerHTML = html', '<text>Exportieren 9.6kW Last 730 W</text><text style="display:none">Importiert Loading</text>')
        result = await self.scraper.live(self.browser.page)
        self.assertEqual(result.values['grid_export_power'],9600)
        self.assertEqual(result.values['grid_import_power'],0)
        await flow.evaluate('el => el.querySelector("svg").innerHTML = "<text>Exportieren 0 W Importiert 730 W Last 730 W</text>"')
        result = await self.scraper.live(self.browser.page)
        self.assertEqual(result.values['grid_import_power'],730)
        self.assertEqual(result.values['grid_export_power'],0)

    async def test_refuses_wrong_range_and_incomplete_energy_distribution(self):
        await self.fixture()
        with self.assertRaises(ValueError):
            await self.scraper.day_energy(self.browser.page,date(2020,1,1))
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el => el.remove()')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page,self.day)
        self.assertEqual(failure_details(caught.exception)['reason'], 'distribution_energy_incomplete')
        self.assertEqual(failure_details(caught.exception)['field'], 'consumption_card')
        self.assertEqual(failure_details(caught.exception)['missing_fields'], ['grid_import_energy'])

    async def test_missing_labels_identify_the_failed_card(self):
        await self.fixture()
        await self.browser.page.locator('#distribution-component-produktion [data-tip]').evaluate_all('els=>els.forEach(el=>el.remove())')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(failure_details(caught.exception)['reason'], 'distribution_labels_missing')
        self.assertEqual(failure_details(caught.exception)['field'], 'production_card')

    async def test_invalid_tooltip_quantity_identifies_the_energy_field(self):
        await self.fixture()
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el=>el.dataset.tip="Vom Netz: Loading"')
        with self.assertRaises(ParseError) as caught:
            await self.scraper.day_energy(self.browser.page, self.day)
        self.assertEqual(failure_details(caught.exception)['reason'], 'quantity_missing')
        self.assertEqual(failure_details(caught.exception)['field'], 'grid_import_energy')

    async def test_return_from_past_day_waits_for_energy_not_just_date_input(self):
        await self.fixture()
        await self.browser.page.get_by_test_id('dashboard-date-range-input').fill('01.01.2020 – 01.01.2020')
        await self.browser.page.evaluate('''today => {
          document.querySelector('[data-testid="today-button"]').onclick=()=>{
            document.querySelector('[data-testid="dashboard-date-range-input"]').value=today;
            document.querySelector('#dashboard-kpis span').textContent='Loading';
            setTimeout(()=>{document.querySelector('#dashboard-kpis span').textContent='10 kWh';},300);
          };
        }''',self.date_text)
        await self.scraper.select_today(self.browser.page)
        self.assertIn('10 kWh',await self.browser.page.locator('#dashboard-kpis').inner_text())

    async def test_zero_production_does_not_require_nonexistent_pv_slice(self):
        await self.fixture(production='0')
        await self.browser.page.locator('#distribution-component-produktion [data-tip]').evaluate_all('els=>els.forEach(el=>el.remove())')
        await self.browser.page.locator('[data-tip="Aus PV-Energie: 5 kWh"]').evaluate('el=>el.remove()')
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el=>{el.dataset.tip="Vom Netz: 10 kWh";el.textContent="100%";}')
        sample = await self.scraper.day_energy(self.browser.page,self.day)
        self.assertEqual(sample.values['grid_import_energy'],10)
        self.assertEqual(sample.values['grid_export_energy'],0)
