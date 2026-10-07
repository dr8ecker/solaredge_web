# Copyright (c) 2026 8ecker.de
"""Phase 1–2 runner: page loading, bounded backoff and clean shutdown."""

import argparse
import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __copyright__, __version__
from .browser import BrowserManager
from .config import Config, ConfigurationError
from .files import write_private_json
from .health import HealthManager
from .logging_config import configure_logging
from .diagnostics import failure_details, runtime_details

LOGGER = logging.getLogger(__name__)
BACKOFF = (10, 30, 60, 120, 300)


def retry_delay(failures: int) -> int:
    return BACKOFF[min(max(failures - 1, 0), len(BACKOFF) - 1)]


async def wait_or_stop(stop: asyncio.Event, seconds: float, health: HealthManager) -> None:
    deadline = time.monotonic() + seconds
    while not stop.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=min(10, remaining))
        except asyncio.TimeoutError:
            health.update()


async def load_or_stop(browser: BrowserManager, stop: asyncio.Event) -> dict | None:
    async def attempt():
        if not getattr(browser, 'usable', browser.connected):
            await browser.close()
            await browser.start()
        return await browser.load_monitoring()

    loading = asyncio.create_task(attempt())
    stopping = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait((loading, stopping), return_when=asyncio.FIRST_COMPLETED)
        if stop.is_set():
            return None
        return await loading
    finally:
        for task in (loading, stopping):
            if not task.done():
                task.cancel()
        await asyncio.gather(loading, stopping, return_exceptions=True)


async def run(config: Config, *, once: bool = False) -> int:
    if config.mode != 'smoke_test':
        from .runner import run_normal
        return await run_normal(config, once=once)
    health = HealthManager(config)
    health.update()
    browser = BrowserManager(config)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows local development; Linux containers use loop handlers.
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    failures = 0
    LOGGER.info("Browser smoke test; no login, dashboard scraping or MQTT in this mode")
    LOGGER.info('Browser runtime: %s', runtime_details())
    try:
        while not stop.is_set():
            attempt = datetime.now(timezone.utc).isoformat()
            health.update(status="loading_page", last_attempt=attempt)
            try:
                result = await load_or_stop(browser, stop)
                if result is None:
                    break
                failures = 0
                challenge = result["signals"]["manual_challenge_visible"]
                terms = result['signals'].get('terms_confirmation_visible', False)
                status = 'terms_confirmation_required' if terms else "manual_login_required" if challenge else "page_loaded"
                write_private_json(config.data_dir / "smoke_report.json", {
                    "mode": "smoke_test", "attempted_at": attempt,
                    "status": status, **result,
                })
                health.update(
                    status=status, last_page_success=time.time(),
                    browser_connected=browser.connected, consecutive_failures=0,
                )
                LOGGER.info("Monitoring page loaded; no dashboard values have been read")
                if config.debug:
                    LOGGER.debug("Page signals: %s", result["signals"])
                if challenge or terms:
                    LOGGER.warning('SolarEdge terms confirmation required; review in your browser and restart the add-on. Automatic page reloads paused' if terms
                                   else "Manual security check detected; automatic page reloads paused")
                    if terms:
                        await browser.idle()
                    if once:
                        return 3
                    while not stop.is_set():
                        health.update(browser_connected=browser.connected)
                        await wait_or_stop(stop, 30, health)
                    break
                if once:
                    return 0
                await browser.idle()
                await wait_or_stop(stop, config.poll_interval, health)
            except ConfigurationError:
                LOGGER.error("Browser configuration is unsupported; check headless and browser_path")
                return 2
            except Exception as error:
                failures += 1
                # Playwright exception messages may contain URLs with tokens or
                # input values. Log only their class, never repr/traceback.
                LOGGER.warning("Browser page-load failed (%s); retry with bounded backoff", type(error).__name__)
                LOGGER.warning('Browser failure details: %s', {**failure_details(error), 'stage':browser.stage, **runtime_details()})
                health.update(
                    status="error", consecutive_failures=failures,
                    browser_connected=browser.connected,
                )
                if once:
                    return 1
                await browser.idle()
                await wait_or_stop(stop, retry_delay(failures), health)
    finally:
        try:
            await browser.close()
        finally:
            health.update(status="offline", browser_connected=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SolarEdge UI-only Home Assistant add-on")
    parser.add_argument("--options", type=Path, default=Path("/data/options.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("/data/runtime"))
    parser.add_argument("--once", action="store_true", help="One page-load attempt; return an exit code")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config = Config.load(args.options, data_dir=args.data_dir)
    except ConfigurationError as error:
        # ConfigurationError contains fixed field names, never supplied values.
        print(f"ERROR: {error}", flush=True)
        return 2
    configure_logging(config)
    LOGGER.info("SolarEdge Web Scraper %s · %s", __version__, __copyright__)
    try:
        return asyncio.run(run(config, once=args.once))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        LOGGER.error("Application stopped (%s); check writable runtime directory", type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
