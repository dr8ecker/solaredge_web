# Copyright (c) 2026 8ecker.de
"""Production/discovery orchestration; browser, ledger and MQTT stay separate."""

import asyncio
import logging
import signal
import time
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from playwright.async_api import TimeoutError as BrowserTimeoutError

from .browser import BrowserManager, RateLimited
from .discovery import SolarEdgeDiscovery
from .energy import EnergyLedger, LedgerError, daily_values
from .statistics import StatisticsImporter, StatisticsError
from .files import write_private_json
from .health import HealthManager
from .login import SolarEdgeLogin, ManualLoginRequired, AuthenticationError, TermsConfirmationRequired, check_challenge
from .mqtt import MqttPublisher
from .navigator import SolarEdgeNavigator
from .scraper import SolarEdgeScraper
from .schedule import wait_for_poll
from .diagnostics import failure_details, runtime_details

LOGGER = logging.getLogger(__name__)


async def run_normal(config, *, once=False):
    # Imported here to retain the smoke-test public helpers used by tests.
    from .main import retry_delay, wait_or_stop
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    health = HealthManager(config)
    health.update(phase=config.mode)
    browser = BrowserManager(config)
    login = SolarEdgeLogin(config)
    navigator = SolarEdgeNavigator(config)
    scraper = SolarEdgeScraper(config)
    publisher = MqttPublisher(config) if config.mode == 'normal' else None
    ledger = None
    failures = 0
    reported_failures = set()
    importer = StatisticsImporter(config)

    async def heartbeat():
        while not stop.is_set():
            health.update(browser_connected=browser.connected, mqtt_connected=publisher.connected if publisher else None)
            if publisher and publisher.connected:
                publisher.publish_availability()
            await wait_or_stop(stop, 10, health)

    async def cycle_work():
        if not browser.usable:
            await browser.close()
            await browser.start()
        health.update(status='logging_in')
        await login.ensure(browser)
        browser.stage = 'plant_navigation'
        await navigator.open_dashboard(browser.page)
        health.update(status='scraping', last_page_success=time.time())
        page = browser.page
        browser.stage = 'dashboard_scrape'
        if config.mode == 'discovery':
            await SolarEdgeDiscovery(config).collect(page)
            # Also capture the normal UI energy view for selector maintenance.
            try:
                await scraper.select_today(page)
                report = await SolarEdgeDiscovery(config).collect(page)
                write_private_json(config.data_dir / 'discovery_energy_report.json', report)
            except Exception:
                LOGGER.warning('Energy-view discovery incomplete; general DOM report saved')
            await login.save(browser)
            chart = page.get_by_test_id('power-energy-chart-component')
            if await chart.count() == 1:
                target = config.data_dir / 'discovery_energy.png'
                await chart.screenshot(path=str(target))
                os.chmod(target, 0o600)
            return None
        today = await scraper.select_today(page)
        clock_day = datetime.now(ZoneInfo(config.site_timezone)).date()
        if today != clock_day:
            raise ValueError('SolarEdge Today differs from site_timezone; no energy published')
        live = await scraper.live(page)
        samples = [await scraper.day_energy(page, today)]
        observed_at = datetime.now(timezone.utc)
        if observed_at.astimezone(ZoneInfo(config.site_timezone)).date() != today:
            raise ValueError('Day changed during scrape; retry before updating counters')
        required = set(ledger.needed_days(today))
        if required:
            day = today
            while day > min(required):
                day -= timedelta(days=1)
                await scraper.previous_day(page, day)
                if day in required:
                    samples.append(await scraper.day_energy(page, day))
        totals, warnings = ledger.apply(samples, observed_at=observed_at)
        values = {k:v for k,v in live.values.items() if k != 'scraped_at'}
        values.update(totals, **daily_values(samples[0]), energy_date=today.isoformat(),
                      energy_gap_count=len(ledger.state['gaps']))
        for warning in warnings:
            LOGGER.warning('%s', warning)
        if live.warnings:
            LOGGER.warning('Optional DOM fields unavailable: %s; run mode=discovery if persistent', ', '.join(live.warnings))
        await login.save(browser)
        write_private_json(config.data_dir / 'last_scrape.json', {
            'scraped_at':datetime.now(timezone.utc).isoformat(), 'day':today.isoformat(),
            'values':values, 'missing_live_fields':live.warnings,
            'energy_gaps':ledger.state['gaps'],
        })
        if config.debug:
            await SolarEdgeDiscovery(config).collect(page)
        return values

    async def cycle():
        try:
            return await cycle_work()
        except (BrowserTimeoutError, ValueError):
            # A dialog may arrive while navigation or a hover is waiting. Report
            # the human action instead of treating it as another load failure.
            if browser.usable:
                try:
                    await check_challenge(browser.page)
                except ManualLoginRequired:
                    raise
                except Exception:
                    pass
            raise

    task_heartbeat = asyncio.create_task(heartbeat())
    try:
        LOGGER.info('Browser runtime: %s', runtime_details())
        if publisher:
            ledger = EnergyLedger(config)
            await publisher.start()
            publisher.update({'history_import_status': 'waiting' if config.history_import else 'disabled'})
        while not stop.is_set():
            started = time.monotonic()
            attempt = datetime.now(timezone.utc).isoformat()
            health.update(status='scraping', last_attempt=attempt, next_poll_at=None)
            if publisher:
                publisher.update({'scraper_last_attempt':attempt, 'scraper_status':'scraping'})
            loading = asyncio.create_task(cycle())
            stopping = asyncio.create_task(stop.wait())
            try:
                await asyncio.wait((loading, stopping), return_when=asyncio.FIRST_COMPLETED)
                if stop.is_set():
                    break
                values = await loading
                failures = 0
                reported_failures.clear()
                success = datetime.now(timezone.utc).isoformat()
                if publisher:
                    await browser.idle()
                    values.update(scraper_last_success=success, scraper_last_attempt=attempt,
                                  scraper_status='connected' if publisher.connected else 'mqtt_disconnected',
                                  scraper_response_time=round(time.monotonic()-started, 2))
                    publisher.update(values, solar_success=True)
                health.update(status='connected' if publisher else 'discovery_complete',
                              last_scrape_success=time.time(), consecutive_failures=0,
                              mqtt_connected=publisher.connected if publisher else None,
                              browser_connected=browser.connected)
                LOGGER.info('Dashboard scrape complete; energy ledger saved' if publisher else 'Discovery complete; private DOM reports saved')
                if publisher:
                    # A HA import outage must not stop normal MQTT publication or
                    # invalidate the successfully scraped SolarEdge values.
                    try:
                        result = await asyncio.to_thread(importer.sync, ledger.state)
                        imported = {'history_import_status': result}
                        if result == 'ok':
                            imported['history_last_success'] = datetime.now(timezone.utc).isoformat()
                        publisher.update(imported)
                    except StatisticsError as error:
                        publisher.update({'history_import_status': 'error'})
                        LOGGER.warning('%s; MQTT values preserved, history retries next cycle', str(error))
                # --once must confirm MQTT delivery, not just enqueue packets.
                if once and publisher:
                    deadline = time.monotonic() + 15
                    while not publisher.connected and time.monotonic() < deadline:
                        await asyncio.sleep(0.1)
                    if not publisher.connected:
                        LOGGER.warning('Scrape saved but MQTT delivery could not be confirmed')
                        return 1
                    packet = publisher.publish(publisher.base + '/availability', 'online')
                    await asyncio.to_thread(packet.wait_for_publish, 10)
                if once or config.mode == 'discovery':
                    return 0
                await wait_for_poll(stop, config.poll_interval, config.site_timezone, health)
            except RateLimited:
                LOGGER.warning('SolarEdge UI rate limit; waiting at least 30 minutes')
                health.update(status='rate_limited', consecutive_failures=config.max_retries)
                if publisher:
                    publisher.update({'scraper_status':'rate_limited'})
                    publisher.unavailable()
                if once:
                    return 1
                await browser.idle()
                await wait_or_stop(stop, max(1800, config.poll_interval), health)
            except (ManualLoginRequired, AuthenticationError, LedgerError) as error:
                status = ('terms_confirmation_required' if isinstance(error, TermsConfirmationRequired)
                          else 'manual_login_required' if isinstance(error, ManualLoginRequired)
                          else 'login_required' if isinstance(error, AuthenticationError) else 'energy_ledger_error')
                LOGGER.error('%s', str(error))
                health.update(status=status, consecutive_failures=config.max_retries)
                if publisher:
                    publisher.update({'scraper_status':status})
                    publisher.unavailable()
                if isinstance(error, TermsConfirmationRequired):
                    await browser.idle()
                if once:
                    return 3
                if isinstance(error, LedgerError) or isinstance(error, ManualLoginRequired):
                    # No automatic security challenge submissions or meter resets.
                    while not stop.is_set():
                        await wait_or_stop(stop, 30, health)
                    break
                await browser.idle()
                await wait_or_stop(stop, max(1800, config.poll_interval), health)
            except Exception as error:
                failures += 1
                LOGGER.warning('Dashboard attempt failed (%s); no zero values published', type(error).__name__)
                details = {**failure_details(error), 'stage':browser.stage, 'browser_connected':browser.connected,
                           'page_crashed':browser.page_crashed, **runtime_details()}
                LOGGER.warning('Dashboard failure details: %s', details)
                if isinstance(error, ValueError):
                    signature = (details['reason'], details.get('field'), tuple(details.get('missing_fields', ())))
                    if browser.stage == 'dashboard_scrape' and browser.usable and signature not in reported_failures:
                        try:
                            # Preserve the failed UI before idle discards it. One
                            # bounded report per reason until the next success.
                            await asyncio.wait_for(SolarEdgeDiscovery(config).collect(
                                browser.page, filename='dashboard_failure_report.json', failure=details),
                                timeout=min(10, config.page_timeout / 1000))
                            reported_failures.add(signature)
                            LOGGER.warning('Private dashboard failure report saved: dashboard_failure_report.json')
                        except Exception as diagnostic_error:
                            LOGGER.warning('Dashboard failure report unavailable: %s', failure_details(diagnostic_error))
                    LOGGER.warning('DOM/date/energy validation failed (%s); use mode=discovery for further inspection', details['reason'])
                health.update(status='error', consecutive_failures=failures, last_failure=details)
                if publisher:
                    publisher.update({'scraper_status':'error'})
                    if failures >= config.max_retries:
                        publisher.unavailable()
                if once:
                    return 1
                await browser.idle()
                await wait_or_stop(stop, retry_delay(failures), health)
            finally:
                for task in (loading, stopping):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(loading, stopping, return_exceptions=True)
    except LedgerError as error:
        LOGGER.error('%s', str(error))
        return 3
    except Exception as error:
        LOGGER.error('Startup failed (%s); check MQTT options and persistent data', type(error).__name__)
        return 2
    finally:
        stop.set()
        task_heartbeat.cancel()
        await asyncio.gather(task_heartbeat, return_exceptions=True)
        if publisher:
            publisher.update({'scraper_status':'offline'})
            await publisher.close()
        await browser.close()
        health.update(status='offline', browser_connected=False, mqtt_connected=False if publisher else None)
    return 0
