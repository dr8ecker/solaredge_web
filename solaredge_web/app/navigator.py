# Copyright (c) 2026 8ecker.de
"""Choose the configured plant through the regular rendered plant list."""

import asyncio

from playwright.async_api import TimeoutError as BrowserTimeoutError

from .diagnostics import dashboard_wait
from .login import check_challenge
from .selectors import SELECTORS


class SolarEdgeNavigator:
    def __init__(self, config):
        self.config = config

    async def open_dashboard(self, page):
        await check_challenge(page)
        picker = page.locator(SELECTORS['date_picker'][0])
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.config.page_timeout / 1000
        while not await picker.is_visible():
            matches = []
            for frame in page.frames:
                if not frame.is_detached():
                    target = frame.get_by_text(self.config.plant_name, exact=True).filter(visible=True)
                    count = await target.count()
                    if count > 1:
                        raise ValueError("Plant name is ambiguous")
                    if count == 1:
                        matches.append(target)
            if len(matches) > 1:
                raise ValueError("Plant name is ambiguous")
            if matches:
                with dashboard_wait('plant_selection_click'):
                    await matches[0].click()
                break
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ValueError("Configured plant not uniquely found")
            await asyncio.sleep(min(0.2, remaining))
        with dashboard_wait('dashboard_date_picker'):
            await picker.wait_for(state='visible')
        with dashboard_wait('dashboard_kpis'):
            await page.locator(SELECTORS['kpis'][0]).wait_for(state='visible')
        # A configured direct dashboard URL must not silently select a different
        # plant just because it has the expected chart structure.
        name = page.get_by_text(self.config.plant_name, exact=True).filter(visible=True)
        try:
            await name.first.wait_for(state='visible')
        except BrowserTimeoutError:
            raise ValueError('Dashboard plant name not confirmed') from None
        await check_challenge(page)
