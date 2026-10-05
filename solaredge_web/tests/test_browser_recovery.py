# Copyright (c) 2026 8ecker.de
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from playwright.async_api import Error

from app.browser import BrowserManager
from app.config import Config
from app.diagnostics import failure_details
from app.runner import run_normal
from app.parser import ParseError, ValueParser
from app.models import ScrapeResult
from datetime import datetime
from zoneinfo import ZoneInfo


class DiagnosticTests(unittest.TestCase):
    def test_validation_reasons_and_fields_never_echo_untrusted_text(self):
        for error in (ValueError('PRIVATE https://secret.test/?token=SECRET'),
                      ParseError('PRIVATE', field='SECRET')):
            details = failure_details(error)
            self.assertEqual(details['kind'], 'validation')
            self.assertEqual(details['reason'], 'unknown_validation')
            self.assertNotIn('field', details)
            for secret in ('PRIVATE', 'SECRET', 'secret.test'):
                self.assertNotIn(secret, json.dumps(details))
        error = ParseError('Distribution does not match displayed total', field='production_card')
        self.assertEqual(failure_details(error)['reason'], 'distribution_total_mismatch')
        self.assertEqual(failure_details(error)['field'], 'production_card')
        self.assertEqual(failure_details(ValueError('Energy cards and production KPI disagree; page still loading'))['reason'], 'production_kpi_mismatch')
        self.assertEqual(failure_details(ValueError('Selector missing or ambiguous: kpis; run mode=discovery'))['field'], 'kpis')

    def test_quantity_diagnostics_distinguish_absent_ambiguous_and_invalid_numbers(self):
        for text, reason in (('Loading', 'quantity_missing'),
                             ('5 kWh 6 kWh', 'quantity_ambiguous'),
                             ('1.2.3 kWh', 'ambiguous_numeric_separators')):
            with self.subTest(text=text), self.assertRaises(ParseError) as caught:
                ValueParser.parse(text, 'kWh', field='production_card')
            details = failure_details(caught.exception)
            self.assertEqual(details['reason'], reason)
            self.assertEqual(details['field'], 'production_card')

    def test_extracts_safe_network_code_without_url_or_call_log(self):
        error = Error('Page.goto: net::ERR_NAME_NOT_RESOLVED at https://example.test/?token=PRIVATE\nCall log: password=SECRET user@example.test')
        details = failure_details(error)
        self.assertEqual(details['network_code'],'ERR_NAME_NOT_RESOLVED')
        text = json.dumps(details)
        for secret in ('PRIVATE','SECRET','example.test','password','https'):
            self.assertNotIn(secret,text)

    def test_unrecognized_network_code_and_message_never_leave_classifier(self):
        details = failure_details(Error('net::ERR_PRIVATE_SECRET at https://secret.test'))
        self.assertIsNone(details['network_code'])
        self.assertNotIn('PRIVATE',json.dumps(details))
        self.assertEqual(failure_details(Error('Page.goto: Page crashed'))['kind'],'page_crashed')


class BrowserRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.manager = BrowserManager(Config(data_dir=Path(self.directory.name),page_timeout=5000))

    async def asyncTearDown(self):
        await self.manager.close()

    async def test_failed_idle_drops_browser_and_restarts_without_crashing(self):
        await self.manager.start()
        browser = self.manager.browser
        self.manager.page.goto = AsyncMock(side_effect=Error('Page.goto: Page crashed'))
        self.assertFalse(await self.manager.idle())
        self.assertIsNone(self.manager.browser)
        self.assertIsNone(self.manager.playwright)
        self.assertFalse(browser.is_connected())
        await self.manager.start()
        await self.manager.page.set_content('<p>Recovered</p>')
        self.assertTrue(self.manager.usable)

    async def test_closed_page_does_not_count_as_a_usable_browser(self):
        await self.manager.start()
        await self.manager.page.close()
        self.assertTrue(self.manager.connected)
        self.assertFalse(self.manager.usable)
        self.assertFalse(await self.manager.idle())
        self.assertFalse(self.manager.connected)

    async def test_normal_runner_retries_navigation_and_idle_failure(self):
        # Model the user's failure sequence, without contacting SolarEdge:
        # live browser handle, failed navigation, failed about:blank navigation.
        async def fake_start():
            self.manager.browser=Mock(is_connected=Mock(return_value=True),close=AsyncMock())
            self.manager.playwright=Mock(stop=AsyncMock())
            self.manager.page=Mock(is_closed=Mock(return_value=False),goto=AsyncMock(side_effect=Error('Page crashed')))
        self.manager.start=AsyncMock(side_effect=fake_start)
        login=Mock(ensure=AsyncMock(side_effect=Error('net::ERR_FAILED private-call-log')))
        publisher=Mock(connected=True,start=AsyncMock(),close=AsyncMock())
        retry_calls=0
        async def wait(stop, seconds, health):
            nonlocal retry_calls
            if health.snapshot['status']=='error':
                retry_calls+=1
                if retry_calls==2: stop.set()
                await asyncio.sleep(0)
            else:
                await stop.wait()
        with patch('app.runner.BrowserManager',return_value=self.manager), patch('app.runner.SolarEdgeLogin',return_value=login), patch('app.runner.MqttPublisher',return_value=publisher), patch('app.main.wait_or_stop',side_effect=wait):
            self.assertEqual(await asyncio.wait_for(run_normal(self.manager.config),5),0)
        self.assertEqual(login.ensure.await_count,2)
        self.assertEqual(self.manager.start.await_count,2)
        self.assertEqual(publisher.start.await_count,1)
        self.assertEqual(publisher.close.await_count,1)

    async def test_regular_redirect_interruption_is_verified_by_visible_ui(self):
        await self.manager.start()
        await self.manager.page.set_content('<p>SolarEdge Welcome to Monitoring</p>')
        self.manager.page.goto=AsyncMock(side_effect=Error('Page.goto: net::ERR_ABORTED'))
        result=await self.manager.load_monitoring()
        self.assertTrue(result['signals']['welcome_visible'])
        self.assertIsNone(result['http_status'])

    async def test_validation_failure_saves_the_failed_dom_before_idle_without_publishing_energy(self):
        await self.manager.start()
        await self.manager.page.set_content('<div>Produktion 5 kWh fixture@example.com</div><input type="password" value="PRIVATE"><div style="display:none">123456 W</div>')
        self.manager.start = AsyncMock()
        scraper = Mock(select_today=AsyncMock(return_value=datetime.now(ZoneInfo('Europe/Berlin')).date()),
                       live=AsyncMock(return_value=ScrapeResult()),
                       day_energy=AsyncMock(side_effect=ParseError('Distribution energy incomplete; run discovery', field='consumption_card')))
        publisher = Mock(connected=True, start=AsyncMock(), close=AsyncMock())
        ledger = Mock()
        with patch('app.runner.BrowserManager', return_value=self.manager), \
             patch('app.runner.SolarEdgeLogin', return_value=Mock(ensure=AsyncMock())), \
             patch('app.runner.SolarEdgeNavigator', return_value=Mock(open_dashboard=AsyncMock())), \
             patch('app.runner.SolarEdgeScraper', return_value=scraper), \
             patch('app.runner.MqttPublisher', return_value=publisher), \
             patch('app.runner.EnergyLedger', return_value=ledger):
            self.assertEqual(await run_normal(self.manager.config, once=True), 1)
        report_path = self.manager.config.data_dir / 'dashboard_failure_report.json'
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['failure']['reason'], 'distribution_energy_incomplete')
        self.assertEqual(report['failure']['field'], 'consumption_card')
        self.assertTrue(any('5 kWh' in element['text'] for element in report['frames'][0]['elements']))
        for secret in ('PRIVATE', 'fixture@example.com', '123456'):
            self.assertNotIn(secret, json.dumps(report))
        ledger.apply.assert_not_called()
        self.assertFalse(any(call.kwargs.get('solar_success') for call in publisher.update.call_args_list))

    async def test_diagnostic_write_failure_does_not_end_or_flood_retries(self):
        await self.manager.start()
        self.manager.start = AsyncMock()
        self.manager.idle = AsyncMock()
        scraper = Mock(select_today=AsyncMock(side_effect=ParseError('Quantity missing', field='production_kpi')))
        publisher = Mock(connected=True, start=AsyncMock(), close=AsyncMock())
        collect = AsyncMock(side_effect=[OSError('PRIVATE'), {}])
        retries = 0
        async def wait(stop, seconds, health):
            nonlocal retries
            if health.snapshot['status'] == 'error':
                retries += 1
                if retries == 3:
                    stop.set()
                await asyncio.sleep(0)
            else:
                await stop.wait()
        with patch('app.runner.BrowserManager', return_value=self.manager), \
             patch('app.runner.SolarEdgeLogin', return_value=Mock(ensure=AsyncMock())), \
             patch('app.runner.SolarEdgeNavigator', return_value=Mock(open_dashboard=AsyncMock())), \
             patch('app.runner.SolarEdgeScraper', return_value=scraper), \
             patch('app.runner.MqttPublisher', return_value=publisher), \
             patch('app.runner.SolarEdgeDiscovery', return_value=Mock(collect=collect)), \
             patch('app.main.wait_or_stop', side_effect=wait):
            self.assertEqual(await asyncio.wait_for(run_normal(self.manager.config), 5), 0)
        self.assertEqual(scraper.select_today.await_count, 3)
        self.assertEqual(collect.await_count, 2)
