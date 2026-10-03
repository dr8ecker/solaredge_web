# Copyright (c) 2026 8ecker.de
"""Regular, bounded login using verified labels and persistent storage state."""

import asyncio
import logging
import re
from urllib.parse import urlsplit

from .files import write_private_json

LOGGER = logging.getLogger(__name__)


class ManualLoginRequired(RuntimeError):
    pass


class AuthenticationError(RuntimeError):
    pass


async def check_challenge(page):
    # Read rendered UI only. A hidden reCAPTCHA script alone is not a challenge.
    text = await page.locator('body').inner_text()
    if re.search(r'verify you are human|security check|Sicherheitsüberprüfung|captcha|verification code|Bestätigungscode|multi.factor|two.factor|Einmalpasswort', text, re.I):
        raise ManualLoginRequired("Manual security check; restart after resolving login")
    frames = page.locator('iframe[title]')
    for frame in await frames.all():
        if await frame.is_visible() and re.search(r'challenge|captcha', await frame.get_attribute('title') or '', re.I):
            raise ManualLoginRequired("Visible security challenge")


class SolarEdgeLogin:
    def __init__(self, config):
        self.config = config
        self.next_login = 0.0

    async def ensure(self, browser):
        page = browser.page
        await browser.load_monitoring()
        browser.stage = 'session_ui_wait'
        await check_challenge(page)
        # Wait for the shell to finish routing before deciding to log in.
        await page.wait_for_function("""() => document.body &&
          /Anlagen|Sites|Dashboard|Willkommen bei Monitoring|Welcome to Monitoring|Email address|Anmelden|Sign in|Log in/i.test(document.body.innerText)""")
        if await page.get_by_text(re.compile(r'^(Anlagen|Sites)$')).count() or await page.locator('#se-date-range-picker').count():
            LOGGER.info("Stored SolarEdge session accepted")
            return
        if asyncio.get_running_loop().time() < self.next_login:
            raise AuthenticationError("Login cooldown active")
        if not self.config.solar_edge_username or not self.config.solar_edge_password:
            raise AuthenticationError("SolarEdge credentials missing")
        browser.stage = 'login_navigation'
        if self.config.login_url:
            await page.goto(self.config.login_url, wait_until='domcontentloaded')
        elif not await page.get_by_label('Email address', exact=True).count():
            await page.get_by_role('button', name=re.compile(r'^(Anmelden|Sign in|Log in)$', re.I)).click()
        email = page.get_by_label('Email address', exact=True)
        browser.stage = 'login_form_wait'
        await email.wait_for(state='visible')
        await check_challenge(page)
        trusted = {"login.solaredge.com"}
        if self.config.login_url:
            trusted.add(urlsplit(self.config.login_url).hostname)
        if urlsplit(page.url).hostname not in trusted:
            raise AuthenticationError("Unexpected login host; credentials not submitted")
        form = page.locator('form').filter(has=email)
        if await form.count() != 1:
            raise AuthenticationError("Login form is ambiguous; run discovery")
        submit = form.get_by_role('button', name='Sign in', exact=True)
        if await submit.count() != 1:
            raise AuthenticationError("Login action is ambiguous")
        LOGGER.info("Signing in with regular SolarEdge login form")
        browser.stage = 'login_form_fill'
        await email.fill(self.config.solar_edge_username)
        await form.get_by_label('Password', exact=True).fill(self.config.solar_edge_password)
        # Navigation, form waits and fills do not submit credentials. Arm the
        # cooldown only at submission, before click: a failed click may already
        # have sent the form, so its result must still be treated conservatively.
        browser.stage = 'login_submit'
        self.next_login = asyncio.get_running_loop().time() + max(1800, self.config.poll_interval)
        await submit.click()
        browser.stage = 'login_result_wait'
        try:
            await page.wait_for_function("""() => document.body &&
                /Anlagen|Sites|Dashboard|incorrect|invalid password|ungültig|captcha|verification code|Bestätigungscode|security check|multi.factor/i.test(document.body.innerText)""")
        except Exception:
            await check_challenge(page)
            raise AuthenticationError("Login did not reach the monitoring UI") from None
        await check_challenge(page)
        if urlsplit(page.url).hostname != urlsplit(self.config.monitoring_url).hostname or await page.locator('input[type=password]').count():
            raise AuthenticationError("Login failed; check configured credentials")
        authenticated = page.get_by_text(re.compile(r'^(Anlagen|Sites)$'))
        has_plants = any([await target.is_visible() for target in await authenticated.all()])
        if not has_plants and not await page.locator('#se-date-range-picker').count():
            raise AuthenticationError('Login did not produce a confirmed monitoring session')
        self.next_login = 0
        await self.save(browser)
        LOGGER.info("SolarEdge session saved privately")

    async def save(self, browser):
        state = await asyncio.wait_for(browser.context.storage_state(), timeout=10)
        write_private_json(self.config.storage_state_path, state)
