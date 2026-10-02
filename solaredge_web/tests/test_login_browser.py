import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
    async def test_challenge_pauses_before_any_credentials_are_filled(self):
        login=await self.start(path='/challenge')
        with self.assertRaises(ManualLoginRequired): await login.ensure(self.browser)
        self.assertFalse(self.config.storage_state_path.exists())
    async def test_untrusted_login_host_never_receives_credentials(self):
        login=await self.start(login='')
        with self.assertRaises(AuthenticationError): await login.ensure(self.browser)
        self.assertEqual(await self.browser.page.get_by_label('Email address',exact=True).input_value(),'')
