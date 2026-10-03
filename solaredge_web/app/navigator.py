# Copyright (c) 2026 8ecker.de
"""Choose the configured plant through the regular rendered plant list."""

from .login import check_challenge


class SolarEdgeNavigator:
    def __init__(self, config):
        self.config = config

    async def open_dashboard(self, page):
        await check_challenge(page)
        if not await page.locator('#se-date-range-picker').count():
            await page.wait_for_function('name => document.body && document.body.innerText.includes(name)', arg=self.config.plant_name)
            matches = []
            for frame in page.frames:
                target = frame.get_by_text(self.config.plant_name, exact=True)
                count = await target.count()
                if count:
                    if count != 1:
                        raise ValueError("Plant name is ambiguous")
                    matches.append(target)
            if len(matches) != 1:
                raise ValueError("Configured plant not uniquely found")
            await matches[0].click()
        await page.locator('#se-date-range-picker').wait_for(state='visible')
        await page.locator('#dashboard-kpis').wait_for(state='visible')
        # A configured direct dashboard URL must not silently select a different
        # plant just because it has the expected chart structure.
        name = page.get_by_text(self.config.plant_name, exact=True)
        if not any([await target.is_visible() for target in await name.all()]):
            raise ValueError('Dashboard plant name not confirmed')
        await check_challenge(page)
