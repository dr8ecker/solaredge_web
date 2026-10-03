# Changelog

## 0.3.2

- Add-on im App-Store als `stable` gekennzeichnet; Kennzeichnung „Experimentell“ entfernt.
- © 2026 8ecker.de in beiden Dashboard-Karten, Dokumentationen, Benachrichtigungsvorlage, Startprotokoll, Container-Metadaten und Quelldateien ergänzt.
- Info-Seite erklärt Zweck und Ablauf; vollständige Einrichtung, Optionen, Sensoren und Fehlersuche in die Dokumentation verschoben.
- Einheitliche Versionsangabe für das Startprotokoll und die MQTT-Discovery.

## 0.3.1

- Standardintervall 15 Minuten (`poll_interval: 900`). Reguläre Abrufe starten zu festen Viertelstunden bei :00:01, :15:01, :30:01 und :45:01, einschließlich 00:00:01 in der Anlagenzeitzone.
- Sofortiger Abruf beim Start sowie begrenzte Wiederholungen und Schutzpausen bei Fehlern bleiben erhalten. Tageswerte nach Mitternacht erscheinen erst nach erfolgreichem Auslesen; keine künstlichen Nullwerte.
- Gespeicherte Add-on-Optionen bleiben beim Update erhalten. Für den neuen Standard einen bestehenden Wert von `poll_interval: 1800` auf `900` ändern und neu starten. Die Warnschwelle für alte Daten beträgt dann 45 Minuten.
- Transparente Übersicht und Detailkarte mit runden Messwertkacheln und dezenten Konturen; Kartenhintergründe, Schatten, Glasfilter und Diagrammfüllung entfernt. Für das Design den Inhalt beider manuellen Karten durch die aktuelle YAML ersetzen.

## 0.3.0

- Tageswerte für Hausverbrauch, Netzbezug, Einspeisung und PV-Eigenverbrauch sowie Autarkie und Eigenverbrauchsquote; keine zusätzlichen SolarEdge-Abfragen dafür.
- Tageswerte werden nach lokalem Mitternachtswechsel bis zum nächsten Abruf unavailable. Quotienten ohne gültigen Nenner bleiben unavailable.
- Datenzustand mit einer vom Abrufintervall abhängigen Altersschwelle, auch zwischen Abrufen; optionale Handy-Benachrichtigung als HA-Blueprint.
- Tagesgenauer Historienimport über den internen HA-Supervisor-Zugang. Eigene Statistikquellen, idempotente Wiederholungen und korrekte Zuordnung von Ausfalltagen, späten Korrekturen und Zeitumstellungen.
- Bestehende Energie-Ledger werden um Stundenbeobachtungen ergänzt; Gesamtzähler und MQTT-IDs bleiben erhalten. Unbekannte Stundenverteilungen nachgeholter Tage werden nicht erfunden.
- Dashboard um Tagesbilanz, Prozentsätze, Datenzustand, dynamisches Abrufintervall und Importdiagnose erweitert.
- Nach dem Update die **Tagesgenau**-Quellen einmal im Energie-Dashboard auswählen: [Umstellungsanleitung](HISTORY.md). Die normale Dashboard-Karte wird weiterhin als YAML eingefügt.

## 0.2.1

- Browser-Idle-Fehler beenden den Retry-Ablauf nicht mehr. Defekte/geschlossene Seiten werden mit neuem Browser wiederholt.
- Regulär unterbrochene Navigation wartet auf bestätigte UI statt sofort einen konkurrierenden Aufruf zu starten.
- Sichere Fehlerkategorien, Netzwerkcodes, Ausführungsphase und Architektur-/Speicherdiagnose ohne rohe Browsermeldungen.
- Regressionstests für die Folge Navigationsfehler → Idle-Fehler → neuer Versuch.

## 0.2.0

- Normaler SolarEdge-Login, Session-Wiederverwendung und eindeutige Anlagenauswahl.
- Discovery-Modus mit bereinigten privaten DOM-Berichten und Energie-Screenshot.
- Verifizierte DOM-Selektoren, Parser und sichtbare Energie-Tooltips.
- Persistente kWh-Gesamtzähler mit Tageswechsel, begrenztem Nachholen und Schutz gegen falsche Resets.
- MQTT Discovery, retained States, Feldgültigkeit, Last-Will und Wiederverbindung.
- 30-Minuten-Standard, Webseite zwischen Abrufen entladen.
- Login-Cooldown, MFA/CAPTCHA-Pause, Retry und vollständiger Healthcheck.
- Automatische Chromium-/Ledger-/MQTT-Prüfungen und Installationsdokumentation.

## 0.1.0

- Add-on-Grundgerüst, Container-Chromium und öffentlicher Seitentest.

---

© 2026 [8ecker.de](https://8ecker.de)
