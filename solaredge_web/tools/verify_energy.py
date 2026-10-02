"""Explicit developer live validation of date switching, no account-page dump."""
import asyncio
import json
from datetime import timedelta
from pathlib import Path

from app.browser import BrowserManager
from app.config import Config
from app.login import SolarEdgeLogin
from app.navigator import SolarEdgeNavigator
from app.scraper import SolarEdgeScraper
from app.logging_config import configure_logging


async def main():
    config = Config.load(Path('/data/options.json'))
    configure_logging(config)
    browser = BrowserManager(config)
    try:
        await browser.start()
        await SolarEdgeLogin(config).ensure(browser)
        await SolarEdgeNavigator(config).open_dashboard(browser.page)
        scraper = SolarEdgeScraper(config)
        today = await scraper.select_today(browser.page)
        print('FLOW', await browser.page.get_by_test_id('power-flow-live-image').evaluate("el => Array.from(el.querySelectorAll('svg text')).map(x => x.textContent).join(' ')"))
        for day in (today, today-timedelta(days=1), today-timedelta(days=2)):
            if day != today:
                await scraper.previous_day(browser.page, day)
            print('PERIOD', day.isoformat(), 'CARD', await browser.page.locator('#distribution-component-produktion').inner_text(), await browser.page.locator('#distribution-component-verbrauch').inner_text())
            sample = await scraper.day_energy(browser.page, day)
            print('ENERGY', json.dumps({k:str(v) for k,v in sample.values.items()}))
        await scraper.select_today(browser.page)
        print('RETURN_TODAY', str(await scraper.selected_dates(browser.page)))
        sample = await scraper.day_energy(browser.page, today)
        print('RETURN_ENERGY', json.dumps({k:str(v) for k,v in sample.values.items()}))
    finally:
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
