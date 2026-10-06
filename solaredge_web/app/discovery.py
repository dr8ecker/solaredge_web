# Copyright (c) 2026 8ecker.de
"""Inspect visible DOM only. Candidate selectors require later verification."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .files import write_private_json

KEYWORDS = {
    "production": ["Produktion", "Produzieren", "Produzierte Energie", "Live-PV-Erzeugung", "Production", "Producing"],
    "consumption": ["Verbrauch", "Last", "Consumption", "Load"],
    "grid_export": ["Exportieren", "Ins Netz", "Einspeisung", "Export", "Exporting", "Grid Export", "To Grid"],
    "grid_import": ["Importiert", "Importieren", "Vom Netz", "Netzbezug", "Import", "Importing", "Grid Import", "From Grid"],
    "pv_to_home": ["Ins Gebäude", "Aus PV-Energie", "PV Energy", "To Building", "From Solar"],
    "battery": ["Battery", "Charging", "Discharging", "Batterie", "Laden", "Entladen"],
    "status": ["Online", "Offline", "Lokale Zeit", "Aktualisiert", "Heute", "Today", "Updated", "Local time"],
}

DISCOVER_DOM = r"""({keywords}) => {
    const normalize = text => (text || '').replace(/\s+/g, ' ').trim();
    const visible = el => el instanceof Element && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const unit = /[-+]?\d[\d.,\s]*\s*(?:MWh|kWh|Wh|MW|kW|W|%|[°˚º]C|V|Hz)(?![a-zA-Z])/;
    const relevant = text => unit.test(text) || keywords.some(word => text.toLowerCase().includes(word.toLowerCase()));
    const textOf = el => normalize(el?.innerText ?? el?.textContent);
    const safeAttribute = (name, value) => value && value.length < 100 &&
        !/token|session|auth|cookie|password|secret|credential|email|username/i.test(name) &&
        !/@|https?:|[a-f0-9]{24,}|[A-Za-z0-9_+=/-]{40,}/i.test(value);
    const elements = [];
    for (const el of document.querySelectorAll('body *')) {
        if (!visible(el) || /^(INPUT|TEXTAREA|SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName)) continue;
        const text = textOf(el);
        const valueWithNearbyUnit = /^[-+]?\d[\d.,\s]*$/.test(text) && unit.test(textOf(el.parentElement));
        if (!text || text.length > 300 || (!relevant(text) && !valueWithNearbyUnit)) continue;
        // Keep the narrowest visible label/value container instead of dumping
        // every enclosing page section repeatedly.
        if (Array.from(el.children).some(child => visible(child) && textOf(child) === text)) continue;
        const attributes = {};
        for (const attr of el.attributes) {
            if (attr.name.startsWith('data-') && safeAttribute(attr.name, attr.value)) attributes[attr.name] = attr.value;
        }
        let selector = null;
        for (const name of ['data-testid', 'data-test', 'data-qa', 'aria-label', 'id']) {
            const value = el.getAttribute(name);
            if (!safeAttribute(name, value)) continue;
            if (name === 'id' && /^highcharts-|^:r|^_r_/i.test(value)) continue;
            const candidate = `[${name}="${CSS.escape(value)}"]`;
            if (document.querySelectorAll(candidate).length === 1) { selector = candidate; break; }
        }
        let nearby = textOf(el.parentElement);
        let parent = el.parentElement;
        for (let depth = 0; depth < 4 && parent; depth++, parent = parent.parentElement) {
            const context = textOf(parent);
            if (context.length > 1000) break;
            if (keywords.some(word => context.toLowerCase().includes(word.toLowerCase())) && unit.test(context)) {
                nearby = context;
                break;
            }
        }
        elements.push({
            text, tag: el.tagName.toLowerCase(),
            id: safeAttribute('id', el.id) ? el.id : null,
            class: el.className && typeof el.className === 'string' ? el.className.slice(0, 250) : null,
            aria_label: el.getAttribute('aria-label'), role: el.getAttribute('role'),
            data_testid: attributes['data-testid'] || null, data_attributes: attributes,
            parent_text: textOf(el.parentElement).slice(0, 600),
            nearby_text: nearby.slice(0, 1000),
            within_chart: Boolean(el.closest('.highcharts-container')),
            possible_selector: selector,
            selector_status: selector ? 'candidate_unique_in_this_snapshot' : 'relative_label_inspection_required'
        });
        if (elements.length >= 500) break;
    }
    return {elements, truncated: elements.length >= 500};
}"""


class SolarEdgeDiscovery:
    def __init__(self, config, *, keywords=None):
        self.config = config
        self.keywords = KEYWORDS if keywords is None else keywords

    def clean(self, value):
        if isinstance(value, dict):
            return {key: self.clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if not isinstance(value, str):
            return value
        for secret in (self.config.solar_edge_username, self.config.solar_edge_password,
                       self.config.mqtt_username, self.config.mqtt_password):
            if secret:
                value = value.replace(secret, "[redacted]")
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", value)
        value = re.sub(r"https?://\S+", "[redacted-url]", value)
        value = re.sub(r"[A-Za-z0-9_+/=-]{40,}", "[redacted-long-value]", value)
        return value

    async def collect(self, page, *, filename='discovery_report.json', failure=None):
        flat = list(dict.fromkeys(word for words in self.keywords.values() for word in words))
        frames = []
        for frame in page.frames:
            if frame.is_detached():
                continue
            try:
                snapshot = await frame.evaluate(DISCOVER_DOM, {"keywords": flat})
                frames.append({"host": urlsplit(frame.url).hostname, **snapshot})
            except Exception as error:
                frames.append({"host": urlsplit(frame.url).hostname, "error_type": type(error).__name__})
        report = self.clean({
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "visible_rendered_dom", "plant_name": self.config.plant_name,
            "selector_notice": "Candidates observed in the real DOM; not finalized production selectors",
            "frames": frames,
        })
        if failure is not None:
            report['failure'] = self.clean(failure)
        write_private_json(self.config.data_dir / filename, report)
        return report
