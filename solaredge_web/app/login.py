# Copyright (c) 2026 8ecker.de
"""Regular, bounded login using a unique password form and persistent state."""

import asyncio
import logging
import re
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeoutError

from .files import write_private_json

LOGGER = logging.getLogger(__name__)

# Field semantics are shared between the readiness check and the fill step.
# SolarEdge also renders a corporate SSO form; never select a username globally.
USERNAME_INPUT = r"""el => {
    if (!['text', 'email'].includes(el.type)) return false;
    if (el.type === 'email' || el.name.toLowerCase() === 'username' ||
        el.autocomplete.toLowerCase().split(/\s+/).includes('username')) return true;
    const labels = Array.from(el.labels || []).map(label => label.innerText.trim());
    labels.push(el.getAttribute('aria-label') || '');
    labels.push((el.getAttribute('aria-labelledby') || '').split(/\s+/)
        .map(id => document.getElementById(id)?.innerText || '').join(' ').trim());
    return labels.some(label => /^(Email(?: address)?|E[-\s]?Mail(?:[-\s]?Adresse)?|Benutzername|Username)$/i.test(label));
}"""
SUBMIT_SELECTOR = 'button[type="submit" i], button:not([type]), input[type="submit" i]'

# Only fixed flags/counts leave the page. Never return text, field values,
# URLs, cookies or storage contents in login diagnostics.
LOGIN_UI_STATE = r"""monitoringHost => {
    const isUsername = USERNAME_FUNCTION;
    const visible = el => {
        if (!el || getComputedStyle(el).visibility === 'hidden') return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };
    const inputs = Array.from(document.querySelectorAll('input')).filter(visible);
    const email = inputs.some(isUsername);
    const password = inputs.some(el => el.type === 'password');
    const forms = Array.from(document.querySelectorAll('form'));
    const passwordForms = forms.filter(form =>
        Array.from(form.querySelectorAll('input[type="password"]')).some(visible));
    const usernames = form => Array.from(form.querySelectorAll('input')).filter(visible).filter(isUsername);
    const formReady = passwordForms.some(form => usernames(form).length &&
        Array.from(form.querySelectorAll('SUBMIT_BUTTONS')).some(visible));
    const plants = Array.from(document.querySelectorAll('body *')).some(el =>
        /^(Anlagen|Sites)$/.test((el.textContent || '').trim()) && visible(el) &&
        /^(Anlagen|Sites)$/.test((el.innerText || '').trim()));
    const dashboard = visible(document.querySelector('#se-date-range-picker'));
    const challenge = /verify you are human|security check|Sicherheitsüberprüfung|captcha|verification code|Bestätigungscode|multi.factor|two.factor|Einmalpasswort/i.test(document.body?.innerText || '') ||
        Array.from(document.querySelectorAll('iframe[title]')).some(el =>
            visible(el) && /challenge|captcha/i.test(el.title));
    return {
        email_field_visible: email,
        password_field_visible: password,
        password_form_count: passwordForms.length,
        username_candidate_count: passwordForms.reduce((count, form) => count + usernames(form).length, 0),
        login_form_ready: formReady,
        session_indicator_visible: plants || dashboard,
        session_confirmed: location.hostname === monitoringHost && !password && (plants || dashboard),
        challenge_visible: challenge,
        login_button_visible: Array.from(document.querySelectorAll('button,[role=button]')).some(el =>
            visible(el) && /^(Anmelden|Sign in|Log in)$/i.test((el.getAttribute('aria-label') || el.innerText || '').trim())),
        visible_input_count: inputs.length,
        visible_form_count: forms.filter(visible).length
    };
}""".replace('USERNAME_FUNCTION', USERNAME_INPUT).replace('SUBMIT_BUTTONS', SUBMIT_SELECTOR)


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

    async def ui_state(self, page):
        return await page.evaluate(LOGIN_UI_STATE, urlsplit(self.config.monitoring_url).hostname)

    async def log_ui_state(self, page):
        try:
            state = await asyncio.wait_for(self.ui_state(page), timeout=2)
            host = urlsplit(page.url).hostname
            state['host_kind'] = ('monitoring' if host == urlsplit(self.config.monitoring_url).hostname
                else 'solaredge_login' if host == 'login.solaredge.com'
                else 'configured_login' if self.config.login_url and host == urlsplit(self.config.login_url).hostname
                else 'other')
            LOGGER.warning('Login UI state: %s', state)
        except Exception:
            LOGGER.warning('Login UI state unavailable')

    async def wait_for_login_destination(self, page, *, allow_entry=False):
        try:
            await page.wait_for_function(
                '({monitoringHost, allowEntry}) => { const state = (' + LOGIN_UI_STATE + ')(monitoringHost); '
                'return state.session_confirmed || state.login_form_ready || state.challenge_visible || '
                '(allowEntry && state.login_button_visible); }',
                arg={'monitoringHost':urlsplit(self.config.monitoring_url).hostname, 'allowEntry':allow_entry},
                polling=200)
        except BrowserTimeoutError:
            await self.log_ui_state(page)
            raise
        await check_challenge(page)
        return await self.ui_state(page)

    async def login_fields(self, page):
        trusted = {'login.solaredge.com'}
        if self.config.login_url:
            trusted.add(urlsplit(self.config.login_url).hostname)
        if urlsplit(page.url).hostname not in trusted:
            await self.log_ui_state(page)
            raise AuthenticationError('Unexpected login host; credentials not submitted')
        form = page.locator('form').filter(has=page.locator('input[type="password"]:visible'))
        if await form.count() != 1:
            await self.log_ui_state(page)
            raise AuthenticationError('Login password form is ambiguous; credentials not submitted')
        password = form.locator('input[type="password"]:visible')
        usernames = []
        for field in await form.locator('input:visible').all():
            if await field.evaluate(USERNAME_INPUT):
                usernames.append(field)
        if await password.count() != 1 or len(usernames) != 1:
            await self.log_ui_state(page)
            raise AuthenticationError('Login fields are ambiguous; credentials not submitted')
        submit = form.locator(SUBMIT_SELECTOR).filter(visible=True)
        if await submit.count() != 1:
            await self.log_ui_state(page)
            raise AuthenticationError('Login action is ambiguous; credentials not submitted')
        return usernames[0], password, submit

    async def ensure(self, browser):
        page = browser.page
        await browser.load_monitoring()
        browser.stage = 'session_ui_wait'
        # Wait for the shell to finish routing before deciding to log in.
        state = await self.wait_for_login_destination(page, allow_entry=True)
        if state['session_confirmed']:
            self.next_login = 0
            LOGGER.info("Stored SolarEdge session accepted")
            return
        if asyncio.get_running_loop().time() < self.next_login:
            raise AuthenticationError("Login cooldown active")
        if not self.config.solar_edge_username or not self.config.solar_edge_password:
            raise AuthenticationError("SolarEdge credentials missing")
        browser.stage = 'login_navigation'
        if self.config.login_url:
            await page.goto(self.config.login_url, wait_until='domcontentloaded')
        elif not (await self.ui_state(page))['password_field_visible']:
            await page.get_by_role('button', name=re.compile(r'^(Anmelden|Sign in|Log in)$', re.I)).click()
        browser.stage = 'login_form_wait'
        state = await self.wait_for_login_destination(page)
        if state['session_confirmed']:
            self.next_login = 0
            await self.save(browser)
            LOGGER.info('SolarEdge session accepted after login redirect; session saved privately')
            return
        email, password, submit = await self.login_fields(page)
        LOGGER.info("Signing in with regular SolarEdge login form")
        browser.stage = 'login_form_fill'
        await email.fill(self.config.solar_edge_username)
        await password.fill(self.config.solar_edge_password)
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
        state = await self.ui_state(page)
        if urlsplit(page.url).hostname != urlsplit(self.config.monitoring_url).hostname or state['password_field_visible']:
            raise AuthenticationError("Login failed; check configured credentials")
        if not state['session_confirmed']:
            raise AuthenticationError('Login did not produce a confirmed monitoring session')
        self.next_login = 0
        await self.save(browser)
        LOGGER.info("SolarEdge session saved privately")

    async def save(self, browser):
        state = await asyncio.wait_for(browser.context.storage_state(), timeout=10)
        write_private_json(self.config.storage_state_path, state)
