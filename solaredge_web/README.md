# SolarEdge Web Scraper 0.3.1

Das Add-on liest mit Playwright Chromium sichtbare SolarEdge-DOM-Werte und reguläre Energie-Tooltips. Scraper und MQTT sind getrennte Komponenten. Keine SolarEdge API, keine eigenen Requests gegen SolarEdge-Endpunkte, kein Modbus, keine OCR und keine Bildauswertung. Die normale Webseite führt ihre üblichen Browserrequests selbst aus.

## Voraussetzungen und Installation

Home Assistant mit Add-on-Support, MQTT-Integration und Broker, Internet sowie ein SolarEdge-Konto mit Zugriff auf die Anlage. AMD64 und AArch64 werden angeboten; der native AArch64-Lauf ist noch nicht geprüft. Das entpackte Debian/Chromium-Image benötigt ungefähr 2 GB; der erste lokale Build dauert einige Minuten.

Im Add-on-/App-Store das Repository `https://github.com/dr8ecker/solaredge_web` hinzufügen und **SolarEdge Web Scraper** installieren. HACS ist nicht beteiligt. Eine lokale Installation ist durch Kopieren dieses vollständigen Ordners nach `/addons/solaredge_web` und Neuladen des Stores möglich.

## Konfiguration

```yaml
solar_edge_username: "DEIN SOLAREDGE LOGIN"
solar_edge_password: "DEIN SOLAREDGE PASSWORT"
plant_name: "Spaeth"
poll_interval: 900
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
history_import: true
```

| Option | Bedeutung |
| --- | --- |
| SolarEdge-Zugangsdaten | Nur aus Konfiguration; niemals geloggt |
| `plant_name` | Exakter sichtbarer Name; doppelte Namen werden abgelehnt |
| `poll_interval` | Sekunden, 30–3600; Standard 900 (feste Viertelstunden) |
| `mode` | `normal`, `discovery` oder `smoke_test` |
| `mqtt_host` | Leer: Supervisor-MQTT-Dienst; sonst externer Broker |
| `mqtt_tls` | TLS mit Zertifikatsprüfung für manuelle Broker |
| `mqtt_discovery_prefix` | Muss zur MQTT-Integration passen |
| `page_timeout` | Pro Browseraktion, Millisekunden, 5000–120000 |
| `max_retries` | Fehlversuche bis SolarEdge-Sensoren unavailable werden, 1–10 |
| `site_timezone` | Anlagenzeitzone; muss zu SolarEdges Heute-Datum passen |
| `history_import` | Tagesgenaue HA-Statistiken über Supervisor importieren; Standard true |
| `history_days` | Maximal nachgeholte Ausfalltage, 1–31; Standard 7 |
| `login_url`, `browser_path` | Normalerweise leer; nur für bewusste Anpassungen |

MQTT-Zugangsdaten gehören zum Broker und können vom Home-Assistant-Login abweichen. Bei automatischer Supervisor-Konfiguration werden Host, Port, TLS und Zugangsdaten des MQTT-Dienstes benutzt. Ein Add-on je Kombination Konto/Anlagenname starten; diese Kombination bestimmt eine stabile MQTT-Gerätekennung.

## Erster Start und Betrieb

Das Add-on lädt die gespeicherte Session oder meldet sich einmal regulär an, wählt die Anlage und öffnet **Heute/Tag → Energie**. Es prüft das Datum und liest Energie aus den Produktions-/Verbrauchskarten und sichtbaren Hover-Tooltips. Gerundete Prozentanteile werden nicht in kWh umgerechnet.

Die Sensoren erscheinen automatisch. Der erste Gesamtzählerstand enthält den bereits angezeigten aktuellen Tageswert; Home Assistant nutzt ihn als statistischen Ausgangspunkt. Der neue separate Historienimport übernimmt vorhandene Tage einschließlich des bekannten Tagesstands vor dem ersten Abruf. [Einrichtung](HISTORY.md).

Beim Start erfolgt sofort ein Abruf. Mit `poll_interval: 900` starten die folgenden regulären Abrufe zu jeder Viertelstunde bei **:00:01, :15:01, :30:01 und :45:01** in `site_timezone`, einschließlich **00:00:01**. Der Zeitplan richtet sich nach der Uhrzeit; die Dauer eines Abrufs verschiebt die folgenden Termine nicht. Die Werte erscheinen erst, wenn die Webseite erfolgreich ausgelesen wurde. Wiederholungen und Schutzpausen bei Fehlern haben Vorrang vor dem regulären Zeitplan.

**Update von einer älteren Version:** Home Assistant behält gespeicherte Optionen. Für den Viertelstundentakt `poll_interval` auf **900** setzen, speichern und das Add-on neu starten; ein bisheriger Wert von `1800` wird nicht automatisch ersetzt.

Nach jedem Abruf öffnet der Browser `about:blank`, um SolarEdges Hintergrundtimer zu stoppen. Zum nächsten Termin wird die Monitoring-Seite im vorhandenen Kontext erneut geöffnet. Ein erneuter Login erfolgt nur bei ungültiger Session.

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

Für die tagesgenaue Zuordnung im Energie-Dashboard die drei importierten **Tagesgenau**-Quellen auswählen; [Anleitung](HISTORY.md). Die ersten drei MQTT-Gesamtzähler bleiben eine Alternative mit Zuordnung zum Abrufzeitpunkt. Sie besitzen `energy`, `total` und `kWh`, ohne regelmäßige Resets. Den Gesamt-Hausverbrauch nicht zusätzlich als einzelnes Gerät zählen. Ohne Import-/Export-Label bleibt der jeweilige Leistungssensor unavailable, statt die Gegenrichtung als erfundene Null zu veröffentlichen. Die Energiewerte stammen davon unabhängig aus Tages-Tooltips. Keine Batteriesensoren. Details: [ENERGY-DESIGN.md](ENERGY-DESIGN.md).

## Tagesbilanz, Datenzustand und Historie

Ab 0.3.0 kommen zwölf Sensoren hinzu; insgesamt werden 30 Sensoren veröffentlicht:

| Sensor | Bedeutung |
| --- | --- |
| `consumption_energy_today` | Hausverbrauch heute, kWh |
| `grid_import_energy_today` | Netzbezug heute, kWh |
| `grid_export_energy_today` | Einspeisung heute, kWh |
| `self_consumption_energy_today` | Selbst genutzte PV-Energie heute, kWh |
| `autarky_today` | PV-Eigenverbrauch / Hausverbrauch × 100 |
| `self_consumption_ratio_today` | PV-Eigenverbrauch / PV-Erzeugung × 100 |
| `energy_date` | Datum der ausgelesenen Tageswerte |
| `data_freshness` | `fresh`, `updating`, `retrying`, `stale` oder ein konkreter Fehlerzustand |
| `scraper_poll_interval` | Eingestelltes Abrufintervall in Sekunden |
| `scraper_stale_after` | Warnschwelle für das Datenalter in Sekunden |
| `history_import_status` | `ok`, `waiting`, `error`, `disabled` oder `supervisor_required` |
| `history_last_success` | Zeitpunkt des letzten bestätigten Historienimports |

Die Tageswerte stammen aus derselben bereits ausgelesenen Energieansicht. Ein Nenner von null ergibt keinen gültigen Prozentsatz; dieser Sensor bleibt dann unavailable. Am lokalen Tageswechsel werden die Tagesanzeigen bis zum nächsten erfolgreichen Abruf unavailable, sodass der Vortagswert nicht als Heute erscheint. Im Viertelstundentakt startet dieser Abruf um **00:00:01**; seine Ergebnisse liegen erst nach dem Auslesen vor. Eine Null wird nur übernommen, wenn die Webseite sie tatsächlich liefert. Die Gesamtzähler laufen weiter.

Der Datenzustand wird auch zwischen Abrufen geprüft. Die Altersschwelle ist mindestens 15 Minuten oder drei Abrufintervalle; beim Standard von 15 Minuten also **45 Minuten**. Bei einem weiterhin gespeicherten 30-Minuten-Intervall sind es 90 Minuten. Ein einzelner Fehler führt zunächst zu `retrying`, bestätigte Anmeldungshindernisse werden direkt kenntlich gemacht. [Optionale Handy-Benachrichtigung](../blueprints/README.md).

`history_import: true` verwendet den internen HA-Zugang des Supervisors, ohne weiteren Benutzer-Token. Dafür enthält die Add-on-Beschreibung `homeassistant_api: true`. Dieser Zugriff betrifft Home Assistant, nicht SolarEdge. Beim separaten Docker-Betrieb ohne Supervisor `history_import: false` setzen. Details zu Tageszuordnung, Migration, Stundenauflösung und Sicherungen: [HISTORY.md](HISTORY.md).

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
