# Copyright (c) 2026 8ecker.de
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from playwright.async_api import TimeoutError

from app.browser import BrowserManager
from app.config import Config
from app.login import SolarEdgeLogin, TermsConfirmationRequired, check_challenge
from app.main import run
from app.runner import run_normal


class TermsBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(data_dir=Path(self.directory.name), page_timeout=2000,
                             solar_edge_username='fixture@example.test', solar_edge_password='fixture-pass')
        self.browser = BrowserManager(self.config)
        await self.browser.start()
        self.body = ''
        async def serve(route):
            await route.fulfill(content_type='text/html; charset=utf-8', body='<html><body>'+self.body+'</body></html>')
        await self.browser.context.route('**/*', serve)

    async def asyncTearDown(self):
        await self.browser.close()

    @staticmethod
    def terms_dialog(title='We’ve updated our Terms and Conditions', submit='Submit'):
        return f'''<div role="dialog"><h1>{title}</h1>
          <label><input type="checkbox" onchange="window.actions++">I acknowledge the updated terms</label>
          <button onclick="window.actions++">Remind Me Later</button>
          <button onclick="window.actions++">{submit}</button></div>
          <script>window.actions=0;</script>'''

    async def test_english_and_german_terms_pause_before_login_or_confirmation(self):
        for title, submit in (('We’ve updated our Terms and Conditions', 'Submit'),
                              ('Unsere Nutzungsbedingungen wurden aktualisiert', 'Bestätigen')):
            with self.subTest(title=title):
                self.body = self.terms_dialog(title, submit)
                login = SolarEdgeLogin(self.config)
                with self.assertRaises(TermsConfirmationRequired):
                    await login.ensure(self.browser)
                self.assertEqual(login.next_login, 0)
                self.assertEqual(await self.browser.page.evaluate('window.actions'), 0)
                self.assertFalse(await self.browser.page.get_by_role('checkbox').is_checked())
                self.assertFalse(self.config.storage_state_path.exists())

    async def test_hidden_dialog_and_ordinary_terms_link_do_not_pause(self):
        self.body = '<h1>SolarEdge Dashboard</h1><a>Terms and Conditions</a><label><input type="checkbox">Newsletter</label><button>Submit</button>'
        self.body += '<div style="display:none">'+self.terms_dialog()+'</div>'
        await self.browser.page.goto(self.config.monitoring_url)
        await check_challenge(self.browser.page)
        self.assertFalse((await SolarEdgeLogin(self.config).ui_state(self.browser.page))['terms_confirmation_visible'])

    async def test_smoke_report_identifies_brandless_terms_dialog_without_clicks(self):
        self.body = self.terms_dialog()
        self.config = Config(mode='smoke_test', data_dir=Path(self.directory.name), page_timeout=2000)
        with patch('app.main.BrowserManager', return_value=self.browser):
            self.assertEqual(await run(self.config, once=True), 3)
        report = json.loads((self.config.data_dir / 'smoke_report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'terms_confirmation_required')
        self.assertTrue(report['signals']['terms_confirmation_visible'])
        self.assertFalse(report['dashboard_scraped'])

    async def test_late_terms_dialog_replaces_navigation_timeout_and_pauses_retries(self):
        self.body = self.terms_dialog()
        await self.browser.page.goto(self.config.monitoring_url)
        navigator = Mock(open_dashboard=AsyncMock(side_effect=TimeoutError('PRIVATE navigation timeout')))
        login = Mock(ensure=AsyncMock())
        publisher = Mock(connected=True, start=AsyncMock(), close=AsyncMock())
        pauses = 0
        async def wait(stop, seconds, health):
            nonlocal pauses
            if health.snapshot['status'] == 'terms_confirmation_required':
                pauses += 1
                stop.set()
                await asyncio.sleep(0)
            else:
                await stop.wait()
        with patch('app.runner.BrowserManager', return_value=self.browser), \
             patch('app.runner.SolarEdgeLogin', return_value=login), \
             patch('app.runner.SolarEdgeNavigator', return_value=navigator), \
             patch('app.runner.MqttPublisher', return_value=publisher), \
             patch('app.main.wait_or_stop', side_effect=wait):
            self.assertEqual(await asyncio.wait_for(run_normal(self.config), 5), 0)
        self.assertEqual(login.ensure.await_count, 1)
        self.assertEqual(navigator.open_dashboard.await_count, 1)
        self.assertEqual(pauses, 1)
        publisher.update.assert_any_call({'scraper_status': 'terms_confirmation_required'})
        self.assertFalse(any(call.kwargs.get('solar_success') for call in publisher.update.call_args_list))
