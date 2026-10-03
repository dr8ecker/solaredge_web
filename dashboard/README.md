# SolarEdge auf deinem Dashboard

Eine Übersicht mit Tageserzeugung, Hausverbrauch, Netzbezug, Einspeisung, PV-Eigenverbrauch, Autarkie, vier Leistungskacheln, 24-Stunden-Verlauf, Temperatur und Datenzustand. Über das Diagramm-Symbol gelangst du zum Home-Assistant-Energie-Dashboard. Antippen der Werte öffnet ihre Details. Die optionale zweite Karte ergänzt sämtliche Energiezähler und Diagnosewerte; beide Karten zusammen zeigen alle 30 Sensoren.

**Vorschau mit Beispieldaten**, aus der getrennten HA-Testinstanz; Werte und Verlauf sind synthetisch. Deine Karte zeigt die tatsächlichen Sensorwerte.

![SolarEdge-Modul im dunklen Theme mit Beispieldaten](preview-dark.png)

[Vorschau im hellen Theme](preview-light.png) · [Vorschau mit Glas-Theme](preview-glass.png)

Übersicht und Detailkarte sind vollständig transparent, sodass dein Dashboard-Hintergrund sichtbar bleibt. Große Tageswerte stehen in zwei Spalten; Autarkie und Eigenverbrauch haben eigene Prozentanzeigen. Die Messwertkacheln haben runde Ecken und dezente Konturen. Kartenhintergründe, Schatten und Glasfilter werden lokal entfernt; das Diagramm zeigt Linien ohne Flächenfüllung.

## Einfügen

Die Gestaltung benötigt **Add-on ab 0.3.0**. Ersetze den Inhalt der bestehenden Übersicht und der Detailkarte vollständig durch die aktuellen Dateien. Für den neuen Abruf zu festen Viertelstunden brauchst du zusätzlich **Add-on 0.3.1** und `poll_interval: 900`; gespeicherte Werte wie `1800` werden beim Update nicht automatisch geändert. Nach einer Änderung das Add-on neu starten. Die HACS-Erweiterungen bleiben dieselben.

Die Übersicht nutzt **Mushroom**, **mini-graph-card** und **card-mod**. Diese drei Erweiterungen sind in deiner gezeigten HACS-Liste bereits vorhanden. card-mod setzt die transparenten Flächen und runden Konturen um. Zusätzliche Helfer sind nicht erforderlich.

1. Dein normales Dashboard öffnen, **⋮ → Dashboard bearbeiten → Karte hinzufügen** wählen.
2. Ganz unten **Manuell** auswählen.
3. Den Inhalt von [solaredge-overview.yaml](solaredge-overview.yaml) vollständig in den Karteneditor kopieren, vorhandenen Text ersetzen und speichern. Im GitHub-Dateifenster öffnet **Raw** den reinen Text.
4. Für die Zähler und alle übrigen Werte eine weitere manuelle Karte mit [solaredge-details.yaml](solaredge-details.yaml) hinzufügen.

**Die Dateien sind einzelne Karten.** Nicht in `configuration.yaml` oder in den YAML-Editor des gesamten Dashboards einfügen. Neue Sensoren werden vom Add-on ab 0.3.0 automatisch über MQTT angelegt. In einem Dashboard mit Abschnitten kann die Übersicht für mehr Platz über die Layout-Einstellungen auf die volle Abschnittsbreite gesetzt werden.

## Was du siehst

| Anzeige | Sensor / Bedeutung |
| --- | --- |
| Große Zahl | `sensor.solaredge_energy_today`: PV-Erzeugung heute in kWh |
| PV-Leistung | `sensor.solaredge_pv_power`: Leistung beim letzten Abruf |
| Hausverbrauch | `sensor.solaredge_consumption_power`: Verbrauchsleistung beim letzten Abruf |
| Netzbezug / Einspeisung | Jeweilige Leistungswerte beim letzten Abruf |
| Diagramm | PV- und Hausleistung aus deiner HA-Historie, in kW, vergangene 24 Stunden |
| Tagesbilanz | Heute verbrauchte, bezogene, eingespeiste und selbst genutzte Energie in kWh |
| Autarkie | Anteil des Hausverbrauchs, den die PV deckt |
| Eigenverbrauch | Anteil der PV-Erzeugung, den das Haus selbst nutzt |
| Status | Datenzustand einschließlich Alter und notwendiger Anmeldung |
| Datenstand | Zeitpunkt des letzten erfolgreichen Abrufs in deiner HA-Zeitzone |
| Zähler & Details | Fünf Energiezähler seit Einrichtung sowie Anlagen- und Abrufinformationen |

Ab Add-on 0.3.1 startet der Standardabruf alle **15 Minuten** zu **:00:01, :15:01, :30:01 und :45:01**, auch um **00:00:01** in der Anlagenzeitzone. Beim Start erfolgt sofort ein Abruf; Wiederholungen und Schutzpausen bei Fehlern können vom Zeitplan abweichen. Die Fußzeile zeigt das tatsächlich eingestellte Intervall. Die Leistungen sind Momentaufnahmen; die Kurven verbinden erfasste Werte und erlauben keine Aussage über die Leistung zwischen den Abrufen. Neue Installationen müssen erst Historie sammeln. Der Verlauf benötigt Home Assistants Recorder; die beiden Leistungssensoren dürfen dort nicht ausgeschlossen sein.

Fehlende Daten werden nicht als Null dargestellt. SolarEdge zeigt möglicherweise nur die gerade aktive Netzrichtung an; die andere Leistungskachel kann dann **nicht verfügbar** sein. Die Tagesbilanz kommt unabhängig davon aus den Energiewerten. Prozentsätze bleiben bei einem Nenner von null unavailable. Die Tageswerte werden am lokalen Mitternachtswechsel bis zum nächsten erfolgreichen Abruf unavailable. Im Viertelstundentakt beginnt dieser um 00:00:01; seine Messwerte erscheinen erst nach dem Auslesen der Webseite.

Der Statuschip berücksichtigt das Alter seit dem letzten erfolgreichen Abruf. Die Warnschwelle kommt vom Add-on und ist mindestens 15 Minuten oder drei Abrufintervalle, beim 15-Minuten-Standard also **45 Minuten**. Bei einem weiterhin gespeicherten 30-Minuten-Intervall sind es 90 Minuten. Die Fußzeile zeigt das tatsächliche Abrufintervall sowie Fehler beim Historienimport. [Optionale Benachrichtigung aufs Handy](../blueprints/README.md).

Die Gesamtzähler stehen bewusst separat als **Energiezähler seit Einrichtung**. Es sind weder Tageswerte noch die gesamte historische Produktion deiner Anlage. Für Tages-, Wochen- und Monatsbilanzen verwende das reguläre [Energie-Dashboard](../README.md#energie-dashboard) mit den [tagesgenauen Statistikquellen](../solaredge_web/HISTORY.md).

## Wenn eine Karte oder ein Wert fehlt

- **„Custom element doesn't exist“:** Die genannte Erweiterung in HACS öffnen, ihre Dashboard-Ressource prüfen und den Browser vollständig neu laden. Die drei benötigten Ressourcen müssen als JavaScript-Module eingebunden sein. `mod-card` gehört zu card-mod.
- **„Entität nicht verfügbar“ / fehlender Wert:** Unter **Einstellungen → Geräte & Dienste → Entitäten** nach `solaredge` suchen. Die Dateien verwenden die Standard-IDs des Add-ons. Wenn HA einen Suffix wie `_2` vergeben hat oder du Sensoren umbenannt hast, ersetze die betreffende ID überall in beiden Dateien. Das gilt auch für IDs in den Textvorlagen.
- **Leeres Diagramm:** Erst nach erfolgreichen Abrufen und gespeicherter Historie erscheinen Punkte. Prüfe Recorder und Sensor-IDs. Diese Karte startet keine zusätzlichen SolarEdge-Abfragen.
- **Andere Farbgestaltung:** Die Karten sind transparent; sichtbar ist dein Dashboard-Hintergrund. Text und dezente Konturen folgen dem hellen oder dunklen HA-Theme. Die Symbolfarben werden direkt gesetzt, damit PV goldfarben und Hausverbrauch türkis bleiben, auch wenn das Theme Farbnamen umdefiniert. card-mod entfernt Kartenhintergründe, Schatten und Glasfilter nur innerhalb dieser SolarEdge-Karten.
- **Kleine Tageszahl oder fehlende Formatierung:** Die aktuelle Übersicht setzt die Überschrift zusätzlich über die gemeinsame Kartenhülle. Ersetze den kompletten Karteninhalt durch die aktuelle Datei und lade den Browser vollständig neu (am PC etwa mit **Strg+F5**). Die in HACS angezeigte Version allein bestätigt nicht, dass der Browser bereits die aktuelle Erweiterung geladen hat. Wenn Formatierung weiterhin fehlt, die Dashboard-Ressourcen auf doppelte oder veraltete card-mod-Einträge prüfen; siehe die [Hinweise des card-mod-Projekts zu Versionen und Cache](https://github.com/thomasloven/lovelace-card-mod#installing).

## Prüfung

Beide Dateien lassen sich als YAML laden und verwenden ausschließlich die 30 vom Add-on veröffentlichten Sensoren. Die Vorlagen wurden in einer getrennten Home-Assistant-Instanz mit Zahlen, echten Nullwerten, fehlenden Werten sowie alten und fehlenden Abrufzeitpunkten geprüft.

Die transparenten Karten wurden in Home Assistant 2026.9.4 mit Mushroom 5.2.3, mini-graph-card 0.13.0 und card-mod 4.2.1 dargestellt. Die Browserprüfung umfasste helles und dunkles Theme, ein zusätzliches Glas-Theme mit eigenen Kartenrahmen sowie schmale Bildschirmbreiten bis 360 px. Auch ein Glas-Theme mit priorisierten Hintergrundregeln wurde geprüft. Die Detailkarte lädt ihre Formatierung über dieselbe `mod-card`-Hülle wie die Übersicht. Lange Zustände können umbrechen; die Leistungsbeschriftung „Haus“ spart auf schmalen Karten Platz. Die Vorschau verwendet ausschließlich Beispieldaten, keine Zugangsdaten oder echten Anlagenwerte. Versionsbezogene Prüfergebnisse stehen in [VALIDATION.md](../solaredge_web/VALIDATION.md).

Die große Tageszahl wurde zusätzlich ohne die lokalen Markdown-Stile geprüft; die Hülle stellt ihre Größe weiterhin korrekt ein. Eine geänderte Theme-Farbe für Amber verändert die direkt gesetzte PV-Symbolfarbe nicht.

Die Kartentypen sind anhand ihrer offiziellen Dokumentation konfiguriert: [Mushroom](https://github.com/piitaya/lovelace-mushroom), [mini-graph-card](https://github.com/kalkih/mini-graph-card), [card-mod](https://github.com/thomasloven/lovelace-card-mod).

---

© 2026 [8ecker.de](https://8ecker.de)
