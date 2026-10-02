"""Actual Chromium against local fixtures, not claimed SolarEdge DOM samples."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.browser import BrowserManager
from app.config import Config
from app.discovery import SolarEdgeDiscovery
from app.main import load_or_stop, run


class FixtureHandler(BaseHTTPRequestHandler):
    ticks = 0
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/tick":
            type(self).ticks += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path == "/error":
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Unavailable")
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/?code=PRIVATE_TOKEN")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if self.path == "/polling":
            self.wfile.write(b"<html><body>SolarEdge<script>window.ticks=0;setInterval(() => {window.ticks++;fetch('/tick');},100);</script></body></html>")
        elif self.path == "/challenge":
            self.wfile.write(b"<html><body>Verify you are human</body></html>")
        else:
            # Simulates client rendering after DOMContentLoaded.
            self.wfile.write(b"<html><body><p>Loading...</p><script>setTimeout(() => {document.body.innerHTML = '<h1>SolarEdge</h1><p>Willkommen bei Monitoring</p><button>Anmelden</button>';}, 150);</script></body></html>")


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.manager = None

    async def asyncTearDown(self):
        if self.manager:
            await self.manager.close()

    async def start(self, path="/"):
        self.manager = BrowserManager(Config(
            monitoring_url=self.origin + path, data_dir=Path(self.directory.name), page_timeout=5000,
        ))
        await self.manager.start()

    async def test_waits_for_rendered_text_and_reuses_context(self):
        await self.start()
        result = await self.manager.load_monitoring()
        self.assertTrue(result["signals"]["welcome_visible"])
        self.assertTrue(result["signals"]["login_text_visible"])
        self.assertFalse(result["dashboard_scraped"])
        context = self.manager.context
        await self.manager.context.add_cookies([{"name": "fixture", "value": "persisted", "url": self.origin}])
        await self.manager.load_monitoring()
        self.assertIs(context, self.manager.context)
        self.assertTrue(any(cookie["name"] == "fixture" for cookie in await context.cookies()))

    async def test_http_failure_is_not_success(self):
        await self.start("/error")
        with self.assertRaises(RuntimeError):
            await self.manager.load_monitoring()

    async def test_report_does_not_expose_redirect_tokens(self):
        await self.start("/redirect")
        result = await self.manager.load_monitoring()
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(result))
        self.assertEqual(result["destination_host"], "127.0.0.1")

    async def test_marks_visible_manual_challenge(self):
        await self.start("/challenge")
        result = await self.manager.load_monitoring()
        self.assertTrue(result["signals"]["manual_challenge_visible"])

    async def test_existing_session_cookie_is_loaded(self):
        state_path = Path(self.directory.name) / "solaredge_storage_state.json"
        state_path.write_text(json.dumps({"cookies": [{
            "name": "fixture", "value": "existing-session", "domain": "127.0.0.1",
            "path": "/", "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax",
        }], "origins": []}), encoding="utf-8")
        await self.start()
        await self.manager.load_monitoring()
        cookies = await self.manager.context.cookies()
        self.assertEqual(cookies[0]["value"], "existing-session")

    async def test_invalid_state_does_not_crash_browser(self):
        state_path = Path(self.directory.name) / "solaredge_storage_state.json"
        state_path.write_text("{", encoding="utf-8")
        await self.start()
        result = await self.manager.load_monitoring()
        self.assertTrue(result["signals"]["welcome_visible"])

    async def test_runner_reports_http_failure_without_success(self):
        config = Config(mode='smoke_test', monitoring_url=self.origin + "/error", data_dir=Path(self.directory.name))
        self.assertEqual(await run(config, once=True), 1)
        health = json.loads((config.data_dir / "health.json").read_text())
        self.assertIsNone(health["last_page_success"])
        self.assertEqual(health["consecutive_failures"], 1)
        self.assertEqual(health["status"], "offline")

    async def test_runner_marks_challenge_without_login(self):
        config = Config(mode='smoke_test', monitoring_url=self.origin + "/challenge", data_dir=Path(self.directory.name))
        self.assertEqual(await run(config, once=True), 3)
        report = json.loads((config.data_dir / "smoke_report.json").read_text())
        self.assertEqual(report["status"], "manual_login_required")
        self.assertFalse(report["dashboard_scraped"])

    async def test_shutdown_cancels_pending_load(self):
        import asyncio
        from unittest.mock import AsyncMock
        pending = asyncio.Event()
        fake = type("Browser", (), {"connected": True})()
        fake.load_monitoring = AsyncMock(side_effect=pending.wait)
        stop = asyncio.Event()
        running = asyncio.create_task(load_or_stop(fake, stop))
        await asyncio.sleep(0)
        stop.set()
        self.assertIsNone(await asyncio.wait_for(running, 1))

    async def test_discovery_captures_visible_svg_text_and_numeric_children(self):
        await self.start()
        await self.manager.page.set_content('<div data-testid="fixture-flow"><svg><text>Exportieren</text><text>2.5kW</text></svg></div><div>Live-PV-Erzeugung <span data-testid="fixture-value">5.43</span> kW</div>')
        report = await SolarEdgeDiscovery(self.manager.config).collect(self.manager.page)
        texts = {element["text"] for element in report["frames"][0]["elements"]}
        self.assertIn("Exportieren", texts)
        self.assertIn("2.5kW", texts)
        self.assertIn("5.43", texts)

    async def test_discovery_omits_secrets_inputs_and_hidden_values(self):
        await self.start()
        await self.manager.page.set_content('<div data-session-token="private-token">Live-PV-Erzeugung 5 kW fixture-secret fixture@example.com</div><input type="password" value="password-input"><p style="display:none">123456 W</p>')
        config = Config(data_dir=Path(self.directory.name), solar_edge_password="fixture-secret")
        report = await SolarEdgeDiscovery(config).collect(self.manager.page)
        serialized = json.dumps(report)
        for secret in ("fixture-secret", "fixture@example.com", "private-token", "password-input", "123456"):
            self.assertNotIn(secret, serialized)

    async def test_idle_stops_websites_own_background_requests(self):
        import asyncio
        await self.start("/polling")
        await self.manager.load_monitoring()
        await self.manager.page.wait_for_function("() => window.ticks >= 3")
        self.assertGreater(FixtureHandler.ticks, 0)
        context = self.manager.context
        await self.manager.idle()
        # Allow requests already in flight to finish before the observation.
        await asyncio.sleep(0.2)
        ticks = FixtureHandler.ticks
        await asyncio.sleep(0.3)
        self.assertEqual(FixtureHandler.ticks, ticks)
        self.assertIs(self.manager.context, context)


if __name__ == "__main__":
    unittest.main()
