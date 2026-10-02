# Tagesgenaue Energiehistorie ab 0.3.0

Das Add-on kann seine gespeicherten Energietage direkt in die Statistik von Home Assistant übertragen. Nach einem Ausfall erscheinen nachgeholte Energiemengen damit am ursprünglichen Kalendertag. Ein erneuter Import ersetzt dieselben Einträge; er addiert sie nicht nochmals.

## Einmal einrichten

1. Das Add-on auf **0.3.0** aktualisieren und starten. `history_import: true` ist die Standardeinstellung.
2. Beim Gerät **SolarEdge Web Scraper** den Sensor **Historienimport** prüfen. Nach einem erfolgreichen Abruf soll er `ok` anzeigen.
3. **Einstellungen → Dashboards → Energie** öffnen und die bisherigen SolarEdge-Quellen durch folgende Statistiken ersetzen. In der Auswahl nach **Tagesgenau** suchen; hinter dem Namen steht dein Anlagenname.

| Feld | Neue Statistik |
| --- | --- |
| Energie der PV-Erzeugung | SolarEdge PV-Erzeugung · Tagesgenau |
| Aus dem Netz bezogene Energie | SolarEdge Netzbezug · Tagesgenau |
| In das Netz eingespeiste Energie | SolarEdge Einspeisung · Tagesgenau |

Für jede Rolle genau eine Quelle verwenden. Beim Wechsel die vorhandene Quelle bearbeiten, statt dieselbe Energie ein zweites Mal hinzuzufügen. Den Hausverbrauch berechnet das Energie-Dashboard aus Erzeugung, Bezug und Einspeisung. Den Gesamt-Hausverbrauch deshalb nicht zusätzlich als einzelnes Gerät hinzufügen.

Die bisherigen MQTT-Sensoren bleiben vorhanden und behalten ihre IDs. Deren Statistik enthält weiterhin die zum Abrufzeitpunkt beobachteten Zählerzuwächse. Die importierten Quellen haben eigene IDs nach dem Muster `solaredge_web:seweb_<Anlagenkennung>_pv_energy`. Vorhandene fremde Statistiken und deine Dashboard-Einstellungen werden nicht überschrieben.

In Home Assistant 2026.9.4 unterstützen externe Energiestatistiken keinen direkt eingetragenen festen Strompreis oder Preissensor. Für diese Quellen **Kosten nicht erfassen** wählen. Separate importierte Kostenstatistiken sind in dieser Version des Add-ons nicht enthalten.

## Was zeitlich genau ist

- **Tage:** Energiemengen gehören zum ausgelesenen SolarEdge-Tag. Auch nachgeholte Mengen und spätere Aufwärtskorrekturen bleiben dort.
- **Stunden:** Neue Zuwächse erscheinen in der Stunde, in der sie beobachtet wurden. Die 30-Minuten-Abfrage liefert keine lückenlose Leistungskurve.
- **Nachgeholte Tage / alte Daten ohne Stundenbeobachtungen:** Die bekannte Tagesmenge wird in der letzten Stunde ihres Tages verbucht. Eine unbekannte Stundenverteilung wird nicht rekonstruiert.
- **Erster Abruf eines Tages:** Bereits vor diesem Abruf erzeugte oder verbrauchte Energie gehört zum richtigen Tag, kann aber nicht nachträglich auf dessen einzelne Stunden verteilt werden.
- **Zeitzone:** Verwendet `site_timezone`; Home Assistant sollte dieselbe Zeitzone nutzen. Europe/Berlin einschließlich 23- und 25-Stunden-Tagen ist geprüft. Zeitzonen mit Mitternacht zwischen vollen UTC-Stunden werden für diesen Import abgelehnt, statt falsch zugeordnet.

Der Import nutzt die vorhandenen gespeicherten Tage. Er startet keinen zusätzlichen SolarEdge-Historienlauf. Beim normalen Betrieb werden Ausfälle bis zu `history_days` Tagen nachgeholt. Längere Lücken bleiben über **Fehlende Energietage** sichtbar. Alte Tage werden nach mindestens 32 Tagen aus dem lokalen Detailbestand in einen Gesamtstand überführt; bereits importierte HA-Langzeitstatistiken bleiben bestehen.

Bei der ersten Umstellung kann die Anzeige für den Installationstag größer werden: Der Import enthält den bekannten vollständigen Tagesstand. Die bisherige MQTT-Statistik begann hingegen mit dem ersten Zählerstand als Ausgangspunkt.

## Verbindung und Fehler

Das Add-on verwendet ausschließlich den internen Home-Assistant-Zugang des Supervisors. Du brauchst dafür weder einen zusätzlichen API-Schlüssel noch eine weitere Integration. `homeassistant_api: true` in der Add-on-Beschreibung erlaubt diesen Zugriff. SolarEdge wird unverändert über die sichtbare Webseite ausgelesen.

| Historienimport | Bedeutung |
| --- | --- |
| `waiting` | Noch kein erfolgreicher Abruf und Import |
| `ok` | Import durchgeführt und letzte Summen in HA zurückgelesen |
| `error` | Verbindung, Import oder Bestätigung fehlgeschlagen; nächster erfolgreicher Abruf versucht es erneut |
| `disabled` | Über `history_import: false` ausgeschaltet |
| `supervisor_required` | Kein Supervisor-Zugang vorhanden, z.B. beim separaten Docker-Betrieb |

Ein Importfehler unterbricht die MQTT-Werte nicht. Der nächste Import schreibt das gesamte noch verfügbare Zeitfenster erneut, sodass auch vorher teilweise übertragene Daten korrigiert werden. Die Dashboard-Karte zeigt Importfehler in ihrer Fußzeile; die optionale [Benachrichtigungsvorlage](../blueprints/README.md) kann sie melden.

HA-Statistiken und das gesamte Add-on-Verzeichnis `/data` sollten gemeinsam gesichert werden. Nach Wiederherstellung einer leeren HA-Datenbank kann das Add-on nur seine noch vorhandenen detaillierten Tage erneut importieren. Es kann bereits kompaktierte alte Tagesverteilungen nicht wiederherstellen.

Technische Grundlagen: [Supervisor-Verbindung zu HA](https://developers.home-assistant.io/docs/apps/communication/#home-assistant-core), [HA-Statistikmetadaten](https://developers.home-assistant.io/blog/2025/10/16/recorder-statistics-api-changes/).
