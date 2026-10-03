# Copyright (c) 2026 8ecker.de
"""Development probe of public login UI; no cookie/token/HTML output."""

import asyncio
import argparse
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

from app.browser import BrowserManager
from app.config import Config
from app.discovery import SolarEdgeDiscovery
from app.files import write_private_json
from app.logging_config import configure_logging


def redact(text, config):
    for secret in (config.solar_edge_username, config.solar_edge_password):
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
    text = re.sub(r"https?://\S+", "[redacted-url]", text)
    text = re.sub(r"[A-Za-z0-9_+/=-]{40,}", "[redacted-token]", text)
    return text


async def main(authenticate=False, energy=False):
    config = Config.load(Path("/data/options.json"))
    configure_logging(config)
    browser = BrowserManager(config)
    try:
        await browser.start()
        await browser.load_monitoring()
        page = browser.page
        existing_session = bool(await page.get_by_text("Anlagen", exact=True).count())
        if not existing_session:
            await page.get_by_role("button", name=re.compile(r"^(Anmelden|Sign in|Log in)$", re.I)).click()
            await page.locator("input:not([type=hidden])").first.wait_for(state="visible")
        result = await page.evaluate("""() => {
          const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
          return {
            inputs: Array.from(document.querySelectorAll('input')).filter(visible).map(el => ({
              type: el.type, placeholder: el.placeholder,
              aria_label: el.getAttribute('aria-label'),
              labels: Array.from(el.labels || []).map(label => label.innerText)
            })),
            buttons: Array.from(document.querySelectorAll('button')).filter(visible).map(el => el.innerText),
            headings: Array.from(document.querySelectorAll('h1,h2')).filter(visible).map(el => el.innerText)
          };
        }""")
        result["host"] = urlsplit(page.url).hostname
        logging.getLogger("probe").info("Public login UI: %s", json.dumps(result, ensure_ascii=False))
        if authenticate and not existing_session:
            if not config.solar_edge_username or not config.solar_edge_password:
                raise ValueError("Missing configured credentials")
            if await page.evaluate("() => /captcha|verification code|security check|multi.factor/i.test(document.body.innerText)"):
                logging.getLogger("probe").warning("Manual security challenge detected; stopping before login")
                return 3
            # Labels verified against the live public login DOM on 2026-10-02.
            email = page.get_by_label("Email address", exact=True)
            password = page.get_by_label("Password", exact=True)
            form = page.locator("form").filter(has=email)
            if await form.count() != 1:
                raise ValueError("Login form is not unique")
            submit = form.get_by_role("button", name="Sign in", exact=True)
            if await submit.count() != 1:
                raise ValueError("Login submit is not unique")
            await email.fill(config.solar_edge_username)
            await password.fill(config.solar_edge_password)
            await submit.click()
            await page.wait_for_function("""() => document.body &&
              /ANLAGENNAME|SITE NAME|Site Name|Anlagen|Sites|Dashboard|verification code|Bestätigungscode|incorrect|invalid password|ungültig|captcha|multi.factor|security check/i.test(document.body.innerText)""",
              timeout=config.page_timeout)
            if urlsplit(page.url).hostname != "monitoring.solaredge.com":
                logging.getLogger("probe").warning("Authentication did not reach the monitoring host; stopping")
                return 3
        if authenticate:
            if await page.locator('input[type="password"]').count():
                raise ValueError("Login form is still present")
            logging.getLogger("probe").info("Monitoring shell reached; inspecting rendered frames")
            for frame in page.frames:
                try:
                    text = redact(await frame.locator("body").inner_text(timeout=5000), config)
                    logging.getLogger("probe").info("Frame UI (%s): %s", urlsplit(frame.url).hostname, text[:5000])
                except Exception:
                    logging.getLogger("probe").info("Frame still loading")
            logging.getLogger("probe").info("Saving regular browser storage state")
            try:
                state = await asyncio.wait_for(browser.context.storage_state(), timeout=10)
            except asyncio.TimeoutError:
                logging.getLogger("probe").warning("Storage snapshot timed out; preserving cookies only")
                state = {"cookies": await browser.context.cookies(), "origins": []}
            write_private_json(config.storage_state_path, state)
            try:
                await page.wait_for_function("name => document.body && document.body.innerText.includes(name)",
                                             arg=config.plant_name, timeout=config.page_timeout)
                matches = []
                for frame in page.frames:
                    target = frame.get_by_text(config.plant_name, exact=True)
                    if await target.count():
                        matches.append(target)
                if len(matches) != 1:
                    raise ValueError("Configured plant was not found in exactly one frame")
                await matches[0].wait_for(state="visible")
            except Exception:
                overview = redact(await page.locator("body").inner_text(), config)
                for frame in page.frames:
                    if frame != page.main_frame:
                        overview += "\nFRAME:\n" + redact(await frame.locator("body").inner_text(timeout=5000), config)
                logging.getLogger("probe").warning("Plant selection not confirmed; visible overview: %s", overview[:6000])
                write_private_json(config.data_dir / "live_login_report.json", {
                    "authentication_confirmed": True, "plant_confirmed": False,
                    "host": urlsplit(page.url).hostname, "visible_text_sample": overview[:6000],
                })
                return 4
            plant = matches[0]
            if await plant.count() != 1:
                raise ValueError("Configured plant is not unique")
            # Authentication is confirmed by the live plant list and absence
            # of a password form, not just a redirect URL.
            if await page.locator('input[type="password"]').count():
                raise ValueError("Login form is still present")
            write_private_json(config.storage_state_path, await browser.context.storage_state())
            visible_text = redact(await page.locator("body").inner_text(), config)
            logging.getLogger("probe").info("Post-login visible UI: %s", visible_text[:3500])
            write_private_json(config.data_dir / "live_login_report.json", {
                "host": urlsplit(page.url).hostname,
                "visible_text_sample": visible_text[:5000],
                "authentication_confirmed": True,
                "plant_confirmed": config.plant_name,
            })
            await plant.click()
            await page.wait_for_function("""() => document.body &&
                /[0-9][.,0-9\\s]*(?:kW|MW|kWh|MWh|Wh|°C)/.test(document.body.innerText)""",
                timeout=config.page_timeout)
            logging.getLogger("probe").info("Dashboard visible UI: %s", redact(await page.locator("body").inner_text(), config)[:6000])
            report = await SolarEdgeDiscovery(config).collect(page)
            logging.getLogger("probe").info("Real DOM discovery saved: %s relevant elements", sum(len(frame.get("elements", [])) for frame in report["frames"]))
            if energy:
                # These IDs/testids came from the saved real DOM discovery,
                # not from screenshots or guessed SolarEdge markup.
                await page.wait_for_function("() => { const text = document.querySelector('#dashboard-kpis')?.innerText || ''; return text.includes('kWh') && /[0-9]/.test(text); }")
                before = await page.locator("#dashboard-kpis").inner_text()
                controls = await page.locator("#se-date-range-picker").evaluate("""el => ({
                    text: el.innerText,
                    controls: Array.from(el.querySelectorAll('button,input,[role=combobox]')).map(item => ({
                        tag: item.tagName, role: item.getAttribute('role'), text: item.innerText,
                        aria_label: item.getAttribute('aria-label'), testid: item.getAttribute('data-testid'),
                        value: item.tagName === 'INPUT' ? item.value : null
                    }))
                })""")
                logging.getLogger("probe").info("Actual date controls: %s", json.dumps(controls, ensure_ascii=False))
                await page.get_by_test_id("today-button").click()
                await page.wait_for_function("old => { const text = document.querySelector('#dashboard-kpis')?.innerText || ''; return text !== old && text.includes('kWh') && /[0-9]/.test(text); }", arg=before)
                logging.getLogger("probe").info("Confirmed Today KPI: %s", await page.locator("#dashboard-kpis").inner_text())
                chart = page.get_by_test_id("power-energy-chart-component")
                buttons = await chart.get_by_role("button").all_text_contents()
                logging.getLogger("probe").info("Energy chart buttons: %s", buttons)
                energy_button = chart.get_by_role("button", name="Energie", exact=True)
                if await energy_button.count() == 1:
                    await energy_button.click()
                    await page.wait_for_function("() => /kWh|KWh|Wh/.test(document.querySelector('[data-testid=\"power-energy-chart-component\"]')?.innerText || '')")
                logging.getLogger("probe").info("Today energy chart text: %s", await chart.inner_text())
                logging.getLogger("probe").info("Confirmed date range: %s", await page.get_by_test_id("dashboard-date-range-input").input_value())
                combo = page.locator("#se-date-range-picker").get_by_role("combobox")
                if await combo.count() == 1:
                    await combo.click()
                    await page.get_by_role("listbox").wait_for(state="visible")
                    periods = await page.get_by_role("option").all_text_contents()
                    logging.getLogger("probe").info("Actual period options: %s", periods)
                    await page.keyboard.press("Escape")
                today_report = await SolarEdgeDiscovery(config).collect(page)
                write_private_json(config.data_dir / "discovery_today_report.json", today_report)
                for component in ("distribution-component-produktion", "distribution-component-verbrauch"):
                    card = page.locator("#" + component)
                    details = await card.evaluate("""el => Array.from(el.querySelectorAll('svg text, svg path')).map(item => ({
                        tag: item.tagName, text: item.textContent,
                        class: item.getAttribute('class'), aria_label: item.getAttribute('aria-label'), role: item.getAttribute('role')
                    }))""")
                    logging.getLogger("probe").info("Actual distribution DOM %s: %s", component, json.dumps(details, ensure_ascii=False))
                    # Hover only the rendered percentage labels; read normal
                    # visible tooltips, never graph internals or geometry.
                    await page.wait_for_function("id => /[0-9]+%/.test(document.getElementById(id)?.innerText || '')", arg=component)
                    for label in await card.get_by_text(re.compile(r"^[0-9]+%$")).all():
                        old_text = await page.locator("body").inner_text()
                        try:
                            await label.hover(timeout=5000)
                            tooltip = page.get_by_role("tooltip")
                            await tooltip.wait_for(state="visible", timeout=5000)
                            percent = (await label.inner_text()).strip()
                            await page.wait_for_function("percent => Array.from(document.querySelectorAll('[role=tooltip]')).some(el => el.getClientRects().length && el.innerText.trim().startsWith(percent + ' '))", arg=percent, timeout=5000)
                            tooltip_text = await tooltip.inner_text()
                            logging.getLogger("probe").info("Visible distribution tooltip: %s", tooltip_text)
                            write_private_json(config.data_dir / (component + "-" + percent.replace('%', '') + ".json"), {
                                "date_range": await page.get_by_test_id("dashboard-date-range-input").input_value(),
                                "tooltip_text": tooltip_text, "source": "visible_ui_tooltip",
                            })
                        except Exception:
                            logging.getLogger("probe").info("No visible tooltip for this percentage label")
                await combo.click()
                await page.get_by_role("option", name="Lebensdauer", exact=True).click()
                await page.wait_for_function("() => { const text = document.querySelector('#dashboard-kpis')?.innerText || ''; return /MWh/.test(text) && /[0-9]/.test(text); }")
                logging.getLogger("probe").info("Lifetime KPI: %s", await page.locator("#dashboard-kpis").inner_text())
                logging.getLogger("probe").info("Lifetime date range: %s", await page.get_by_test_id("dashboard-date-range-input").input_value())
                lifetime_report = await SolarEdgeDiscovery(config).collect(page)
                write_private_json(config.data_dir / "discovery_lifetime_report.json", lifetime_report)
    except Exception as error:
        logging.getLogger("probe").error("Login UI probe failed (%s)", type(error).__name__)
        return 1
    finally:
        await browser.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--authenticate", action="store_true")
    parser.add_argument("--energy", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.authenticate, args.energy)))
