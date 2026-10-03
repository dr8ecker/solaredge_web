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

    async def test_nominal_rating_is_not_the_pv_measurement(self):
        await self.fixture()
        result = await self.scraper.live(self.browser.page)
        self.assertEqual(result.values['pv_power'],2400)
        self.assertEqual(result.values['grid_import_power'],810)
        self.assertNotIn('grid_export_power',result.values)

    async def test_refuses_wrong_range_and_incomplete_energy_distribution(self):
        await self.fixture()
        with self.assertRaises(ValueError):
            await self.scraper.day_energy(self.browser.page,date(2020,1,1))
        await self.browser.page.locator('[data-tip="Vom Netz: 5 kWh"]').evaluate('el => el.remove()')
        with self.assertRaises(ParseError):
            await self.scraper.day_energy(self.browser.page,self.day)

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
