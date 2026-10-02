# Changelog

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
