"""Keep one Chromium context. Never call SolarEdge endpoints directly."""

import json
import asyncio
import logging
import os
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from .config import Config, ConfigurationError
from .diagnostics import failure_details

LOGGER = logging.getLogger(__name__)


class RateLimited(RuntimeError):
    pass


class BrowserManager:
    def __init__(self, config: Config):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.page_crashed = False
        self.stage = 'not_started'

    @property
    def connected(self) -> bool:
        return bool(self.browser and self.browser.is_connected())

    @property
    def usable(self) -> bool:
        return bool(self.connected and self.page and not self.page.is_closed() and not self.page_crashed)

    def on_page_crash(self, *_):
        self.page_crashed = True
        LOGGER.warning('Chromium page crashed; browser will be restarted on the next attempt')

    async def start(self) -> None:
        self.stage = 'browser_start'
        if not self.config.headless and os.name != "nt" and not os.getenv("DISPLAY"):
            raise ConfigurationError("headless=false requires a local graphical display")
        self.playwright = await async_playwright().start()
        try:
            options = {
                "headless": self.config.headless,
                # Supervisor typically provides only 64 MB /dev/shm. Chromium
                # uses /tmp instead; no host IPC or privileged mode is needed.
                "args": ["--disable-dev-shm-usage"],
                "env": {k:v for k,v in os.environ.items() if k not in {"SUPERVISOR_TOKEN", "HASSIO_TOKEN"}},
            }
            if self.config.browser_path:
                options["executable_path"] = self.config.browser_path
            self.browser = await self.playwright.chromium.launch(**options)
            state = None
            path = self.config.storage_state_path
            if path.exists():
                try:
                    if path.is_symlink() or path.stat().st_size > 5_000_000:
                        raise ValueError("Unsafe session file")
                    state = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(state, dict):
                        raise ValueError("Invalid session file")
                    LOGGER.info("Loading stored browser session; validity is not yet verified")
                except (OSError, ValueError):
                    LOGGER.warning("Stored browser session is unreadable; starting a fresh context")
                    state = None
            context_options = {"locale": "de-DE", "timezone_id":self.config.site_timezone, "viewport": {"width": 1440, "height": 1000}}
            if state is not None:
                context_options["storage_state"] = state
            try:
                self.context = await self.browser.new_context(**context_options)
            except Exception:
                if state is None:
                    raise
                LOGGER.warning("Stored browser session is incompatible; starting a fresh context")
                context_options.pop("storage_state")
                self.context = await self.browser.new_context(**context_options)
            self.context.set_default_timeout(self.config.page_timeout)
            self.context.set_default_navigation_timeout(self.config.page_timeout)
            self.page = await self.context.new_page()
            self.page_crashed = False
            self.page.on('crash', self.on_page_crash)
            LOGGER.info("Chromium started in %s mode", "headless" if self.config.headless else "visible")
        except BaseException:
            await self.close()
            raise

    async def load_monitoring(self) -> dict:
        """A page-load test, not proof of login or a completed dashboard scrape."""
        self.stage = 'monitoring_navigation'
        try:
            response = await self.page.goto(self.config.monitoring_url, wait_until="domcontentloaded")
        except Exception as error:
            if failure_details(error)['network_code'] != 'ERR_ABORTED' or not self.usable:
                raise
            # A regular client-side redirect can interrupt goto. Confirm the
            # rendered UI below rather than start a competing navigation.
            LOGGER.info('Monitoring navigation interrupted by redirect; waiting for visible UI')
            response = None
        if response is not None and response.status == 429:
            raise RateLimited('Monitoring UI rate limit; automatic loading delayed')
        if response is not None and response.status >= 400:
            raise RuntimeError("Monitoring page returned an HTTP error")
        # Wait for supplied public entry-page wording rather than a transient
        # "Loading" splash. These are UI text signals, not dashboard selectors.
        # Unknown pages fail the test instead of being reported as a ready UI.
        self.stage = 'monitoring_ui_wait'
        await self.page.wait_for_function(
            """() => document.body &&
                /SolarEdge|Willkommen bei Monitoring|Welcome to Monitoring|Anmelden|Sign in|Log in|Anlagen|Sites|Dashboard|verify you are human|bestätigen.{0,30}Mensch|enter.{0,20}verification code|Bestätigungscode eingeben|security check|Sicherheitsüberprüfung/i.test(document.body.innerText)""",
            timeout=self.config.page_timeout,
        )
        signals = await self.page.evaluate("""() => {
            const text = document.body.innerText;
            return {
                solaredge_brand_visible: /SolarEdge/i.test(text),
                welcome_visible: /Willkommen bei Monitoring|Welcome to Monitoring/i.test(text),
                login_text_visible: /Anmelden|Sign in|Log in/i.test(text),
                plants_text_visible: /Anlagen|Sites/i.test(text),
                manual_challenge_visible: /verify you are human|bestätigen.{0,30}Mensch|enter.{0,20}verification code|Bestätigungscode eingeben|security check|Sicherheitsüberprüfung/i.test(text)
            };
        }""")
        # Only the origin is returned. Never record a redirect path, query,
        # title, HTML, cookies or raw visible text in this early test mode.
        destination = urlsplit(self.page.url)
        return {
            "destination_host": destination.hostname,
            "http_status": response.status if response is not None else None,
            "browser_version": self.browser.version,
            "signals": signals,
            "dashboard_scraped": False,
        }

    async def close(self) -> None:
        browser, playwright = self.browser, self.playwright
        self.browser = self.context = self.page = self.playwright = None
        self.page_crashed = False
        try:
            if browser:
                await asyncio.wait_for(browser.close(), timeout=10)
        except Exception as error:
            LOGGER.warning('Browser shutdown failed: %s', failure_details(error))
        finally:
            if playwright:
                try:
                    await asyncio.wait_for(playwright.stop(), timeout=10)
                except Exception as error:
                    LOGGER.warning('Browser driver shutdown failed: %s', failure_details(error))

    async def idle(self) -> bool:
        """Stop SolarEdge's own SPA timers between widely spaced polls."""
        self.stage = 'browser_idle'
        try:
            if self.usable:
                await self.page.goto("about:blank", wait_until="domcontentloaded", timeout=min(5000,self.config.page_timeout))
                return True
            if not self.browser and not self.playwright:
                return False
        except Exception as error:
            LOGGER.warning('Unable to idle browser; resetting it without ending retries: %s', failure_details(error))
        await self.close()
        return False
