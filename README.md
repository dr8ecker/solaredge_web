# SolarEdge Web Scraper für Home Assistant

Installierbares Add-on mit Chromium, regulärem SolarEdge-Login, persistenten Energiezählern und MQTT Discovery. Es liest sichtbare Texte der Monitoring-Weboberfläche einschließlich regulärer Energie-Tooltips. Keine SolarEdge Monitoring API, kein API-Key, kein Modbus, keine OCR und keine Diagramm-Pixelanalyse.

## Installation

1. In Home Assistant **Einstellungen → Apps/Add-ons → App-Store → ⋮ → Repositories** öffnen.
2. `https://github.com/dr8ecker/solaredge_web` hinzufügen.
3. **SolarEdge Web Scraper** installieren. Der erste Build lädt Chromium und kann einige Minuten dauern.
4. SolarEdge-Zugangsdaten und den exakten Anlagennamen konfigurieren.
5. MQTT-Integration und Broker einrichten. Bei installiertem Mosquitto-Add-on kann `mqtt_host` leer bleiben; der MQTT-Dienst des Supervisors wird verwendet. Für einen externen Broker Host und Zugangsdaten konfigurieren.
6. Mit `mode: normal` starten. Die Sensoren erscheinen beim Gerät **SolarEdge Web Scraper**.

**HACS wird nicht benötigt.** Home Assistant OS bzw. eine Installation mit Add-on-Support ist erforderlich. Home Assistant Container kann das Image separat starten, besitzt aber keinen Add-on-Store.

## Energie-Dashboard

Unter **Einstellungen → Dashboards → Energie** diese Sensoren zuordnen:

| Verwendung | Standard-Entity-ID |
| --- | --- |
| Solarerzeugung | `sensor.solaredge_pv_energy_total` |
| Stromnetzbezug | `sensor.solaredge_grid_import_energy_total` |
| Stromnetzeinspeisung | `sensor.solaredge_grid_export_energy_total` |

Die Zähler besitzen `device_class: energy`, `state_class: total` und die Einheit kWh. Home Assistant kann bei bestehenden Namen einen Suffix hinzufügen. Nicht die Tagesanzeige oder einen Leistungssensor als Energiezähler verwenden. Der Hausverbrauch ergibt sich aus Erzeugung, Bezug und Einspeisung; den Gesamtverbrauch nicht zusätzlich als einzelnes Gerät hinzufügen.

Alle **30 Minuten** ein Abruf genügt für Energiezuwächse; Leistungswerte bleiben Momentaufnahmen. Zwischen Abrufen wird die Webseite entladen, damit ihre eigenen Aktualisierungstimer keine zusätzliche Last erzeugen. Browser und Session bleiben erhalten.

Die HA-Energiehistorie beginnt mit der Inbetriebnahme. Nachgeholte Tage werden im aktuellen Abruf übernommen, nicht rückwirkend in die ursprünglichen Stunden geschrieben. Drei-Tages- und Wochenansichten werden nicht wiederholt addiert.

## Stand

**0.2.0**, erste experimentelle Version. Login, Session, echte Tageswerte, Datumwechsel, MQTT und Energie-Dashboard wurden in AMD64-Containern mit separatem Home Assistant geprüft. ARM64 lässt sich bauen; ein nativer ARM64-Lauf und die Installation unter dem echten Supervisor sind noch nicht geprüft.

- [Konfiguration, Sensoren und Fehlersuche](solaredge_web/README.md)
- [Energiezähler und Tageswechsel](solaredge_web/ENERGY-DESIGN.md)
- [Prüfungen und Grenzen](solaredge_web/VALIDATION.md)

Zugangsdaten stehen ausschließlich in der privaten Add-on-Konfiguration. Session und Zähler liegen persistent in `/data` und werden nicht hochgeladen. MFA/CAPTCHA wird nicht umgangen.
