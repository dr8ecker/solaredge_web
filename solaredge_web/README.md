# SolarEdge Web Scraper 0.2.1

Das Add-on liest mit Playwright Chromium sichtbare SolarEdge-DOM-Werte und reguläre Energie-Tooltips. Scraper und MQTT sind getrennte Komponenten. Keine SolarEdge API, keine eigenen Requests gegen SolarEdge-Endpunkte, kein Modbus, keine OCR und keine Bildauswertung. Die normale Webseite führt ihre üblichen Browserrequests selbst aus.

## Voraussetzungen und Installation

Home Assistant mit Add-on-Support, MQTT-Integration und Broker, Internet sowie ein SolarEdge-Konto mit Zugriff auf die Anlage. AMD64 und AArch64 werden angeboten; der native AArch64-Lauf ist noch nicht geprüft. Das entpackte Debian/Chromium-Image benötigt ungefähr 2 GB; der erste lokale Build dauert einige Minuten.

Im Add-on-/App-Store das Repository `https://github.com/dr8ecker/solaredge_web` hinzufügen und **SolarEdge Web Scraper** installieren. HACS ist nicht beteiligt. Eine lokale Installation ist durch Kopieren dieses vollständigen Ordners nach `/addons/solaredge_web` und Neuladen des Stores möglich.

## Konfiguration

```yaml
solar_edge_username: "DEIN SOLAREDGE LOGIN"
solar_edge_password: "DEIN SOLAREDGE PASSWORT"
plant_name: "Spaeth"
poll_interval: 1800
headless: true
debug: false
mode: normal
mqtt_host: ""
mqtt_port: 1883
mqtt_tls: false
mqtt_discovery_prefix: homeassistant
mqtt_username: ""
mqtt_password: ""
login_url: ""
monitoring_url: "https://monitoring.solaredge.com/"
browser_path: ""
page_timeout: 30000
max_retries: 5
site_timezone: Europe/Berlin
history_days: 7
```

| Option | Bedeutung |
| --- | --- |
| SolarEdge-Zugangsdaten | Nur aus Konfiguration; niemals geloggt |
| `plant_name` | Exakter sichtbarer Name; doppelte Namen werden abgelehnt |
| `poll_interval` | Sekunden, 30–3600; Standard 1800 |
| `mode` | `normal`, `discovery` oder `smoke_test` |
| `mqtt_host` | Leer: Supervisor-MQTT-Dienst; sonst externer Broker |
| `mqtt_tls` | TLS mit Zertifikatsprüfung für manuelle Broker |
| `mqtt_discovery_prefix` | Muss zur MQTT-Integration passen |
| `page_timeout` | Pro Browseraktion, Millisekunden, 5000–120000 |
| `max_retries` | Fehlversuche bis SolarEdge-Sensoren unavailable werden, 1–10 |
| `site_timezone` | Anlagenzeitzone; muss zu SolarEdges Heute-Datum passen |
| `history_days` | Maximal nachgeholte Ausfalltage, 1–31; Standard 7 |
| `login_url`, `browser_path` | Normalerweise leer; nur für bewusste Anpassungen |

MQTT-Zugangsdaten gehören zum Broker und können vom Home-Assistant-Login abweichen. Bei automatischer Supervisor-Konfiguration werden Host, Port, TLS und Zugangsdaten des MQTT-Dienstes benutzt. Ein Add-on je Kombination Konto/Anlagenname starten; diese Kombination bestimmt eine stabile MQTT-Gerätekennung.

## Erster Start und Betrieb

Das Add-on lädt die gespeicherte Session oder meldet sich einmal regulär an, wählt die Anlage und öffnet **Heute/Tag → Energie**. Es prüft das Datum und liest Energie aus den Produktions-/Verbrauchskarten und sichtbaren Hover-Tooltips. Gerundete Prozentanteile werden nicht in kWh umgerechnet.

Die Sensoren erscheinen automatisch. Der erste Gesamtzählerstand enthält den bereits angezeigten aktuellen Tageswert; Home Assistant nutzt ihn als statistischen Ausgangspunkt. Historie vor Inbetriebnahme wird nicht rückdatiert importiert.

Nach jedem Abruf öffnet der Browser `about:blank`, um SolarEdges Hintergrundtimer zu stoppen. Nach 30 Minuten wird die Monitoring-Seite im vorhandenen Kontext erneut geöffnet. Ein erneuter Login erfolgt nur bei ungültiger Session.

## Sensoren und Energie-Dashboard

Alle folgenden Standard-IDs beginnen mit `sensor.solaredge_`; bei Namenskonflikten vergibt Home Assistant einen Suffix. Alle gehören zum Gerät **SolarEdge Web Scraper**.

| Sensor | Verwendung |
| --- | --- |
| `pv_energy_total` | kWh, Solarerzeugung im Energie-Dashboard |
| `grid_import_energy_total` | kWh, Stromnetzbezug im Energie-Dashboard |
| `grid_export_energy_total` | kWh, Stromnetzeinspeisung im Energie-Dashboard |
| `consumption_energy_total` | kWh, zusätzlicher Gesamtverbrauch |
| `self_consumption_energy_total` | kWh, zusätzlicher PV-Eigenverbrauch |
| `energy_today` | kWh, Tagesanzeige ohne Zähler-State-Class |
| `pv_power`, `consumption_power` | W, aktuelle PV-Leistung und Last |
| `grid_import_power`, `grid_export_power` | W, nur tatsächlich beschriftete Flussrichtung |
| `outside_temperature` | °C |
| `site_status` | Sichtbarer SolarEdge-Status |
| `last_update` | Sichtbarer relativer Aktualisierungstext |
| `scraper_last_success`, `scraper_last_attempt` | UTC-Zeitstempel |
| `scraper_status`, `scraper_response_time` | Status und Abrufdauer in Sekunden |
| `energy_gap_count` | Fehlende Tage außerhalb des Nachholfensters |

Für das Energie-Dashboard nur die ersten drei Zähler zuordnen. Sie besitzen `energy`, `total` und `kWh`, ohne regelmäßige Resets. Den Gesamt-Hausverbrauch nicht zusätzlich als einzelnes Gerät zählen. Ohne Import-/Export-Label bleibt der jeweilige Leistungssensor unavailable, statt die Gegenrichtung als erfundene Null zu veröffentlichen. Die Energiewerte stammen davon unabhängig aus Tages-Tooltips. Keine Batteriesensoren. Details: [ENERGY-DESIGN.md](ENERGY-DESIGN.md).

## Discovery und Debugging

`mode: discovery` durchläuft Login und Navigation und speichert privat unter `/data/runtime`:

- `discovery_report.json`: relevante sichtbare Elemente, Attribute, Kontext und Selektorkandidaten.
- `discovery_energy_report.json`: zusätzliche Energieansicht, falls erreichbar.
- `discovery_energy.png`: Screenshot des Energiebereichs, ohne Loginformular.

Der Discovery-Vorgang endet nach einem Durchlauf. Anschließend `mode: normal` setzen und neu starten. Kandidaten gelten nicht automatisch als geprüfte Selektoren. Die tatsächlich verifizierten Selektoren stehen zentral in `app/selectors.py`, deutsche/englische Keywords in `app/discovery.py`. Die automatische Datumsauswertung unterstützt derzeit das verifizierte deutsche Format `TT.MM.JJJJ – TT.MM.JJJJ`.

`debug: true` erzeugt zusätzlich bereinigte DOM-Berichte nach erfolgreichen normalen Abrufen. Es gibt keinen öffentlichen Diagnose-Webserver und keinen vollständigen HTML-Dump. Screenshots dienen nur zur Diagnose und werden nicht ausgewertet. Berichte können Anlagen-/Energiedaten enthalten; vor Weitergabe prüfen.

`mode: smoke_test` prüft ausschließlich den Browser und die öffentliche Monitoring-Seite. Kein Login, kein Energieabruf, kein MQTT.

## Fehler und Session

Browserfehler erhalten begrenzten Backoff von 10, 30, 60, 120 bis 300 Sekunden. Einzelne Fehler löschen keine Sensoren und senden keine Nullen. Nach `max_retries` oder zu alten Daten werden SolarEdge-Sensoren unavailable. MQTT nutzt retained Discovery/States, individuelle Feldgültigkeit, Last-Will und automatische Wiederverbindung.

Bei einem HTTP-429-Limit im Monitoring-Aufruf pausiert der normale Modus mindestens 30 Minuten.

Unbestätigter Login setzt `login_required` und begrenzt weitere Anmeldeversuche auf frühestens 30 Minuten. MFA/CAPTCHA setzt `manual_login_required` und pausiert bis Neustart. Nötige manuelle Anmeldung muss außerhalb des headless Add-ons stattfinden; kein integriertes Web-VNC und keine Umgehung. Eine autorisierte Playwright-Session kann privat in `solaredge_storage_state.json` bereitgestellt werden.

Bei geänderter Webseite zuerst Discovery-Berichte prüfen. Fehlende/unparsebare Felder werden unavailable; bei einem kompletten fehlgeschlagenen Abruf bleiben vorherige Werte innerhalb der Fehler-Toleranz erhalten. Nie Parsingfehler als Null interpretieren.

Healthcheck: Prozess, Heartbeat, Browser, Alter des letzten erfolgreichen Abrufs und MQTT. Kurze Start-Schonfrist. `health.json` und `last_scrape.json` enthalten keine Zugangsdaten.

Ab 0.2.1 nennt `Dashboard failure details` die Ausführungsphase, eine sichere Fehlerkategorie und bekannte Netzwerkcodes (z.B. `ERR_NAME_NOT_RESOLVED` für DNS), sowie Architektur, gegebenenfalls Container-Speicherlimit und OOM-Kill-Zähler. Rohe Playwright-Meldungen und URLs werden nicht geloggt. Ein fehlgeschlagenes Entladen der Seite beendet den Retry-Ablauf nicht; der defekte Browser wird geschlossen und beim nächsten Versuch neu gestartet.

## Persistenz und Sicherheit

`/data/runtime/solaredge_storage_state.json` enthält sensible Session-Daten und darf nicht veröffentlicht werden. `energy_ledger.json` enthält Energiezähler, `energy_ledger.backup.json` den vorherigen Commit. Dateien werden atomar und privat geschrieben. Chromium läuft als `scraper` (UID 1000), ohne privilegierten Container oder Host-IPC. Playwright nutzt seine übliche Container-Konfiguration ohne Chromium-OS-Sandbox; SolarEdge-Schutzmechanismen werden nicht umgangen.

Bei fehlendem/beschädigtem Ledger nach bekannter Initialisierung wird kein Nullstand veröffentlicht. **Gesamtes `/data` sichern**, zum Beispiel mit der Home-Assistant-Add-on-Sicherung. Wenn alle persistenten Dateien gelöscht werden, ist frühere Initialisierung nicht mehr erkennbar. Ein älteres Backup nicht ungeprüft gegen einen bereits höheren an Home Assistant gemeldeten Zählerstand austauschen.

## Entwicklung

```sh
docker build -t solaredge-web:local .
docker run --rm -v "$PWD/data:/data" solaredge-web:local python -m app.main --once
```

Private `data/options.json` bereitstellen; außerhalb des Supervisors ist ein MQTT-Host nötig. Keine Zugangsdaten in Befehlszeilen. Git/Docker ignorieren private Daten und Entwicklungsumgebungen. GitHub Actions prüft Parser, Zähler, echtes Chromium gegen lokale Testseiten und einen isolierten Mosquitto-Broker ohne SolarEdge-Zugangsdaten. [VALIDATION.md](VALIDATION.md) beschreibt Live-Prüfungen und Grenzen.
