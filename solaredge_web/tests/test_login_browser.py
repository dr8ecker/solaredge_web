# Copyright (c) 2026 8ecker.de
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import Error, TimeoutError

from app.browser import BrowserManager
from app.config import Config
from app.login import SolarEdgeLogin, AuthenticationError, ManualLoginRequired


class LoginFixtureHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.end_headers()
        if self.path == '/challenge':
            body='<h1>SolarEdge security check</h1><p>Enter verification code</p>'
        elif self.path.startswith('/login'):
            bad = self.path == '/login-bad'
            action = "document.body.innerHTML='<p>invalid password</p>'" if bad else "document.cookie='authorized=1; path=/';document.body.innerHTML='<h1>Anlagen</h1><span>Fixture Plant</span>'"
            body=f'''<h1>SolarEdge</h1><form><label>Email address<input type="email"></label><label>Password<input type="password"></label><button>Sign in</button></form>
            <script>window.submissions=0;document.querySelector('form').onsubmit=e=>{{e.preventDefault();window.submissions++;{action};}};</script>'''
        elif 'authorized=1' in self.headers.get('Cookie',''):
            body='<h1>Anlagen</h1><span>Fixture Plant</span>'
        else:
            body='''<h1>SolarEdge</h1><p>Welcome to Monitoring</p><button onclick="location.href='/login'">Sign in</button>'''
        self.wfile.write(('<html><body>'+body+'</body></html>').encode())


class LoginBrowserTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),LoginFixtureHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.browser=None
    async def asyncTearDown(self):
        if self.browser: await self.browser.close()
    async def start(self, *, path='/', login='/login'):
        self.config=Config(monitoring_url=self.origin+path,login_url=self.origin+login if login else '',
                           data_dir=Path(self.directory.name),solar_edge_username='fixture@example.test',
                           solar_edge_password='fixture-pass',page_timeout=5000)
        self.browser=BrowserManager(self.config)
        await self.browser.start()
        return SolarEdgeLogin(self.config)
    async def start_routed(self, pages, *, redirects=None):
        """Exercise the default entry flow with synthetic HTTPS origins only."""
        self.config=Config(data_dir=Path(self.directory.name),
                           solar_edge_username='fixture@example.test',
                           solar_edge_password='fixture-pass',page_timeout=2000)
        self.browser=BrowserManager(self.config)
        await self.browser.start()
        self.submissions=0
        self.posted_forms=[]
        redirects=redirects or {}
        async def serve(route):
            request=route.request
            if request.method == 'POST':
                self.submissions+=1
                self.posted_forms.append(parse_qs(request.post_data or ''))
            target=urlsplit(request.url)
            key=f'{target.scheme}://{target.netloc}{target.path}'
            if key in redirects:
                # Client redirects are separately intercepted too; fulfilled
                # HTTP redirects can cause Chromium to follow outside routing.
                await route.fulfill(content_type='text/html; charset=utf-8',
                                    body='<script>location.replace('+json.dumps(redirects[key])+')</script>')
            else:
                await route.fulfill(status=200 if key in pages else 404,
                                    content_type='text/html; charset=utf-8',
                                    body='<html><body>'+pages.get(key,'Unknown fixture')+'</body></html>')
        # All requests, including accidental unknown targets, stay in the fixture.
        await self.browser.context.route('**/*',serve)
        return SolarEdgeLogin(self.config)
    @staticmethod
    def entry_page(extra=''):
        return ('<p>Welcome to Monitoring</p>'+extra+
                '<button onclick="location.href=\'https://login.solaredge.com/\'">Sign in</button>')
    @staticmethod
    def login_form():
        return '''<h1>SolarEdge</h1>
            <form method="post" action="https://monitoring.solaredge.com/authenticated">
            <label>Email address<input type="email" name="email"></label>
            <label>Password<input type="password" name="password"></label>
            <button>Sign in</button></form>'''
    async def test_default_login_entry_submits_form_once(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':self.login_form(),
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.config.login_url,'')
        self.assertEqual(self.submissions,1)
        self.assertEqual(login.next_login,0)
        self.assertTrue(self.config.storage_state_path.exists())
    async def test_localized_german_login_labels_and_submit_are_supported(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':'''<h1>SolarEdge</h1>
                <form method="post" action="https://monitoring.solaredge.com/authenticated">
                <label>E-Mail-Adresse<input type="text" name="user"></label>
                <label>Passwort<input type="password" name="password"></label>
                <button>Anmelden</button></form>''',
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,1)
        self.assertEqual(self.posted_forms,[{'user':['fixture@example.test'],'password':['fixture-pass']}])
        self.assertEqual(login.next_login,0)
        self.assertTrue(self.config.storage_state_path.exists())
    async def test_unlabelled_email_is_selected_from_password_form_not_corporate_sso(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':'''<h1>SolarEdge</h1>
                <form id="corporate" method="post" action="https://login.solaredge.com/corporate">
                <label>Email address<input type="text" name="corporate-user" autocomplete="username"></label>
                <button>Sign in</button></form>
                <form id="regular" method="post" action="https://monitoring.solaredge.com/authenticated">
                <input type="email" name="username">
                <input type="password" name="password">
                <button>Sign in</button></form>''',
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,1)
        self.assertEqual(self.posted_forms,[{'username':['fixture@example.test'],'password':['fixture-pass']}])
        self.assertEqual(login.next_login,0)
        self.assertTrue(await self.browser.page.get_by_text('Anlagen',exact=True).is_visible())
        self.assertTrue(self.config.storage_state_path.exists())
    async def test_text_username_autocomplete_identifies_unlabelled_login(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':'''<h1>SolarEdge</h1>
                <form method="post" action="https://monitoring.solaredge.com/authenticated">
                <input type="text" name="user" autocomplete="username">
                <input type="password" name="password" autocomplete="current-password">
                <button>Log in</button></form>''',
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,1)
        self.assertEqual(self.posted_forms,[{'user':['fixture@example.test'],'password':['fixture-pass']}])
        self.assertEqual(login.next_login,0)
        self.assertTrue(self.config.storage_state_path.exists())
    async def test_ambiguous_username_fields_reject_before_filling_credentials(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':'''<h1>SolarEdge</h1>
                <form method="post" action="https://monitoring.solaredge.com/authenticated">
                <input type="email" name="first-user">
                <input type="text" name="second-user" autocomplete="username">
                <input type="password" name="password">
                <button>Sign in</button></form>''',
        })
        with self.assertRaises(AuthenticationError):
            await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertFalse(self.config.storage_state_path.exists())
        self.assertEqual(await self.browser.page.locator('input').evaluate_all(
            'inputs => inputs.map(input => input.value)'),['','',''])
    async def test_multiple_password_forms_reject_before_filling_credentials(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':self.login_form()+'''
                <form method="post" action="https://login.solaredge.com/another-login">
                <input type="email" name="another-user">
                <input type="password" name="another-password">
                <button>Sign in</button></form>''',
        })
        with self.assertRaises(AuthenticationError):
            await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertFalse(self.config.storage_state_path.exists())
        self.assertEqual(await self.browser.page.locator('input').evaluate_all(
            'inputs => inputs.map(input => input.value)'),['','','',''])
    async def test_default_entry_accepts_sso_redirect_without_login_form(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        },redirects={
            'https://login.solaredge.com/':'https://monitoring.solaredge.com/authenticated',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertTrue(await self.browser.page.get_by_text('Anlagen',exact=True).is_visible())
        self.assertTrue(self.config.storage_state_path.exists())
    async def test_session_can_finish_routing_after_initial_welcome(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':'''<p>Welcome to Monitoring</p>
                <script>setTimeout(() => {document.body.innerHTML='<h1>Anlagen</h1>';},150);</script>''',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertTrue(await self.browser.page.get_by_text('Anlagen',exact=True).is_visible())
    async def test_challenge_at_login_destination_pauses_before_form_wait(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(),
            'https://login.solaredge.com/':'<h1>Security check</h1><p>Enter verification code</p>',
        })
        with self.assertRaises(ManualLoginRequired):
            await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertFalse(self.config.storage_state_path.exists())
    async def test_hidden_session_indicators_do_not_skip_login(self):
        login=await self.start_routed({
            'https://monitoring.solaredge.com/':self.entry_page(
                '<h1 hidden>Anlagen</h1><div id="se-date-range-picker" hidden></div>'),
            'https://login.solaredge.com/':self.login_form(),
            'https://monitoring.solaredge.com/authenticated':'<h1>Anlagen</h1>',
        })
        await login.ensure(self.browser)
        self.assertEqual(self.submissions,1)
        self.assertTrue(await self.browser.page.get_by_text('Anlagen',exact=True).is_visible())
    async def test_session_text_on_untrusted_host_is_not_accepted(self):
        login=await self.start_routed({
            'https://untrusted.example.test/':'<h1>Anlagen</h1>'+self.login_form(),
        })
        async def load_untrusted_destination():
            await self.browser.page.goto('https://untrusted.example.test/')
        with patch.object(self.browser,'load_monitoring',side_effect=load_untrusted_destination):
            with self.assertRaises(AuthenticationError):
                await login.ensure(self.browser)
        self.assertEqual(self.submissions,0)
        self.assertEqual(login.next_login,0)
        self.assertEqual(await self.browser.page.get_by_label('Email address',exact=True).input_value(),'')
        self.assertFalse(self.config.storage_state_path.exists())
    async def test_login_timeout_diagnostics_include_only_fixed_flags_and_counts(self):
        login=await self.start_routed({
            'https://login.solaredge.com/private-redirect':'''<p>PRIVATE_BODY user@example.test</p>
                <input type="text" value="PRIVATE_USERNAME">
                <input type="password" value="PRIVATE_PASSWORD">
                <script>document.cookie='PRIVATE_COOKIE=PRIVATE_COOKIE_VALUE';
                localStorage.setItem('PRIVATE_STORAGE','PRIVATE_STORAGE_VALUE');</script>''',
        })
        await self.browser.page.goto('https://login.solaredge.com/private-redirect?token=PRIVATE_QUERY')
        with self.assertLogs('app.login',level='WARNING') as captured:
            with self.assertRaises(TimeoutError):
                await login.wait_for_login_destination(self.browser.page)
        output='\n'.join(captured.output)
        self.assertIn("'host_kind': 'solaredge_login'",output)
        self.assertIn("'password_field_visible': True",output)
        self.assertIn("'visible_input_count': 2",output)
        self.assertIn("'email_field_visible': False",output)
        for private in ('PRIVATE_','user@example.test','private-redirect','https://','login.solaredge.com'):
            self.assertNotIn(private,output)
    async def test_normal_login_persists_and_reuses_session(self):
        login=await self.start()
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),1)
        state=json.loads(self.config.storage_state_path.read_text())
        self.assertTrue(any(c['name']=='authorized' for c in state['cookies']))
        await self.browser.close()
        self.browser=BrowserManager(self.config)
        await self.browser.start()
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.get_by_text('Anlagen',exact=True).count(),1)
        self.assertEqual(await self.browser.page.locator('input[type=password]').count(),0)
    async def test_failed_login_does_not_submit_again_in_same_cooldown(self):
        login=await self.start(login='/login-bad')
        with self.assertRaises(AuthenticationError): await login.ensure(self.browser)
        with self.assertRaises(AuthenticationError): await login.ensure(self.browser)
        self.assertGreater(login.next_login,0)
    async def test_monitoring_timeout_does_not_arm_login_cooldown(self):
        login=await self.start()
        with patch.object(self.browser, 'load_monitoring', AsyncMock(side_effect=TimeoutError('UI not ready'))):
            with self.assertRaises(TimeoutError): await login.ensure(self.browser)
        self.assertEqual(login.next_login,0)
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),1)
    async def test_login_navigation_failure_can_retry_without_cooldown(self):
        login=await self.start()
        goto=self.browser.page.goto
        async def fail_login_navigation(url, **options):
            if url == self.config.login_url:
                raise Error('net::ERR_NETWORK_CHANGED')
            return await goto(url, **options)
        with patch.object(self.browser.page, 'goto', side_effect=fail_login_navigation):
            with self.assertRaises(Error): await login.ensure(self.browser)
        self.assertEqual(self.browser.stage,'login_navigation')
        self.assertEqual(login.next_login,0)
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),1)
    async def test_form_wait_timeout_can_retry_without_cooldown(self):
        login=await self.start()
        await self.browser.page.route('**/login', lambda route: route.fulfill(
            content_type='text/html',body='<p>Loading...</p>'))
        with self.assertRaises(TimeoutError): await login.ensure(self.browser)
        self.assertEqual(self.browser.stage,'login_form_wait')
        self.assertEqual(login.next_login,0)
        await self.browser.page.unroute('**/login')
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),1)
    async def test_fill_failure_can_retry_without_cooldown(self):
        login=await self.start()
        from playwright.async_api import Locator
        with patch.object(Locator, 'fill', AsyncMock(side_effect=TimeoutError('Input not ready'))):
            with self.assertRaises(TimeoutError): await login.ensure(self.browser)
        self.assertEqual(self.browser.stage,'login_form_fill')
        self.assertEqual(login.next_login,0)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),0)
        await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.evaluate('window.submissions'),1)
    async def test_uncertain_submission_keeps_cooldown_and_blocks_second_click(self):
        login=await self.start()
        from playwright.async_api import Locator
        click=AsyncMock(side_effect=TimeoutError('Submission result unknown'))
        with patch.object(Locator, 'click', click):
            with self.assertRaises(TimeoutError): await login.ensure(self.browser)
            self.assertEqual(self.browser.stage,'login_submit')
            self.assertGreater(login.next_login,0)
            with self.assertRaisesRegex(AuthenticationError,'Login cooldown active'):
                await login.ensure(self.browser)
        self.assertEqual(click.await_count,1)
    async def test_challenge_pauses_before_any_credentials_are_filled(self):
        login=await self.start(path='/challenge')
        with self.assertRaises(ManualLoginRequired): await login.ensure(self.browser)
        self.assertFalse(self.config.storage_state_path.exists())
    async def test_untrusted_login_host_never_receives_credentials(self):
        login=await self.start(login='')
        with self.assertRaises(AuthenticationError): await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.get_by_label('Email address',exact=True).input_value(),'')
