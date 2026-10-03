# Copyright (c) 2026 8ecker.de
"""Verified live DOM 2026-10-02; semantic fallbacks stay in these scopes.

No generated CSS hashes, absolute XPath, graph internals or network payloads.
"""

SELECTORS = {
    "date_picker": ['#se-date-range-picker'],
    "date_input": ['[data-testid="dashboard-date-range-input"]'],
    "today": ['[data-testid="today-button"]'],
    "previous": ['[data-testid="previous-date"]', '[aria-label="previous period"]'],
    "chart": ['[data-testid="power-energy-chart-component"]'],
    "production_card": ['#distribution-component-produktion'],
    "consumption_card": ['#distribution-component-verbrauch'],
    "kpis": ['#dashboard-kpis'],
    "pv_power": ['[data-testid="current-power-component"]', '#current-power'],
    "nominal_power": ['[data-testid="current-power.nomalized-max-power"]'],
    "flow": ['[data-testid="power-flow-live-image"]'],
    "temperature": ['[data-testid="weather-widget.live-temperature"]'],
    "site_status": ['[id^="site-connectivity-status-"]'],
}


async def unique(page, name):
    for selector in SELECTORS[name]:
        target = page.locator(selector)
        if await target.count() == 1 and await target.is_visible():
            return target
    raise ValueError(f"Selector missing or ambiguous: {name}; run mode=discovery")
