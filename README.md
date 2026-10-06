# SolarEdge Web Scraper für Home Assistant

Installierbares Add-on mit Chromium, regulärem SolarEdge-Login, persistenten Energiezählern und MQTT Discovery. Es liest sichtbare Texte der Monitoring-Weboberfläche einschließlich regulärer Energie-Tooltips. Keine SolarEdge Monitoring API, kein API-Key, kein Modbus, keine OCR und keine Diagramm-Pixelanalyse.

## Installation

1. In Home Assistant **Einstellungen → Apps/Add-ons → App-Store → ⋮ → Repositories** öffnen.
2. `https://github.com/dr8ecker/solaredge_web` hinzufügen.
3. **SolarEdge Web Scraper** installieren. Der erste Build lädt Chromium und kann einige Minuten dauern.
4. SolarEdge-Zugangsdaten und den exakten Anlagennamen konfigurieren.
5. MQTT-Integration und Broker einrichten. Bei installiertem Mosquitto-Add-on kann `mqtt_host` leer bleiben; der MQTT-Dienst des Supervisors wird verwendet. Für einen externen Broker Host und Zugangsdaten konfigurieren.
6. Mit `mode: normal` starten. Die Sensoren erscheinen beim Gerät **SolarEdge Web Scraper**.

**Für das Add-on wird HACS nicht benötigt.** Home Assistant OS bzw. eine Installation mit Add-on-Support ist erforderlich. Home Assistant Container kann das Image separat starten, besitzt aber keinen Add-on-Store.

## Energie-Dashboard

Ab **0.3.0** importiert das Add-on Tageswerte in eigene HA-Statistikquellen. Nach einem erfolgreichen Abruf zeigt der Sensor **Historienimport** `ok`. Unter **Einstellungen → Dashboards → Energie** diese Quellen auswählen:

| Verwendung | Statistikname, ergänzt um deinen Anlagennamen |
| --- | --- |
| Solarerzeugung | SolarEdge PV-Erzeugung · Tagesgenau |
| Stromnetzbezug | SolarEdge Netzbezug · Tagesgenau |
| Stromnetzeinspeisung | SolarEdge Einspeisung · Tagesgenau |

Bei bestehenden Installationen die bisherigen SolarEdge-Quellen durch diese Statistiken ersetzen. Pro Rolle genau eine Quelle verwenden. Der Hausverbrauch ergibt sich aus Erzeugung, Bezug und Einspeisung. [Umstellung, Zeitauflösung und Grenzen](solaredge_web/HISTORY.md).

Die bisherigen MQTT-Gesamtzähler bleiben als Alternative erhalten (`sensor.solaredge_pv_energy_total`, `sensor.solaredge_grid_import_energy_total`, `sensor.solaredge_grid_export_energy_total`). Ihre Zuwächse werden weiterhin zum Abrufzeitpunkt erfasst. Tagesanzeigen und Leistungssensoren sind keine Energie-Summenquellen.

Ab **0.3.1** ist der Standard `poll_interval: 900`: Der Abruf startet zu jeder Viertelstunde bei **:00:01, :15:01, :30:01 und :45:01**, einschließlich **00:00:01** in der Anlagenzeitzone. Beim Start wird sofort abgerufen; nach Fehlern gelten weiterhin die Wiederholungs- und Wartezeiten. Bereits gespeicherte Einstellungen bleiben erhalten: Steht bei dir noch `1800`, ändere den Wert auf `900` und starte das Add-on neu.

Die Messwerte erscheinen nach Abschluss des jeweiligen Abrufs. Auch nach Mitternacht werden keine Nullwerte erfunden. Leistungswerte bleiben Momentaufnahmen. Zwischen Abrufen wird die Webseite entladen, damit ihre eigenen Aktualisierungstimer keine zusätzliche Last erzeugen. Nachgeholte Tagesmengen erscheinen mit den neuen Statistikquellen am ursprünglichen Tag. Die genaue Stundenverteilung vor einem Ausfall lässt sich aus Tageswerten nicht rekonstruieren.

## Dashboard-Karten

[Fertiges SolarEdge-Dashboard-Modul mit Einfüge-Anleitung](dashboard/README.md): Tagesbilanz, Autarkie, Eigenverbrauchsquote, Leistungskacheln, 24-Stunden-Verlauf und Datenzustand. Die Übersicht und die optionale Detailkarte sind transparent; Messwerte stehen in abgerundeten Kacheln mit dezenten Konturen. Nutzt die vorhandenen HACS-Karten Mushroom, mini-graph-card und card-mod.

[Optionale Ausfallmeldung aufs Handy](blueprints/README.md): wählbares Gerät, Wartezeit und Entwarnung.

## Stand

**0.3.9** erkennt zusätzlich die englischen Beschriftungen `From Solar`, `To Building`, `Exporting` und `Importing`. Der mit `From Solar` reproduzierte Fehler bei der Verbrauchsaufteilung ist in lokalen Browser-Tests behoben; die Bestätigung auf dem Nutzergerät steht noch aus. Konkrete Dashboard-Fehlergründe und private Diagnoseberichte stehen seit 0.3.8 bereit.

Login, Session, echte Tageswerte, Datumwechsel, MQTT und Energie-Dashboard wurden für frühere Versionen in AMD64-Containern mit separatem Home Assistant geprüft. Der Nutzer hat auf seinem x86-64-Home-Assistant erfolgreiche MQTT-Verbindung, Chromium-Start, Login und einen vollständigen Abruf mit gespeichertem Energie-Ledger bestätigt. ARM64 lässt sich bauen; ein nativer ARM64-Lauf und mehrtägiger Dauerbetrieb sind noch nicht bestätigt. Die Tageswerte und der Historienimport wurden für 0.3.0 zusätzlich mit echtem SolarEdge-Abruf und einer getrennten HA-Testinstanz geprüft. Einzelne Prüfergebnisse und ihr Versionsstand stehen in [VALIDATION.md](solaredge_web/VALIDATION.md).

- [Konfiguration, Sensoren und Fehlersuche](solaredge_web/DOCS.md)
- [Energiezähler und Tageswechsel](solaredge_web/ENERGY-DESIGN.md)
- [Prüfungen und Grenzen](solaredge_web/VALIDATION.md)

[Copyright-Hinweis](COPYRIGHT.md).

Zugangsdaten stehen ausschließlich in der privaten Add-on-Konfiguration. Session und Zähler liegen persistent in `/data` und werden nicht hochgeladen. MFA/CAPTCHA wird nicht umgangen.

---

© 2026 [8ecker.de](https://8ecker.de)
