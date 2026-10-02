# Validierung 0.2.1

Prüftag: 2026-10-02. Der Live-Test wurde vom Kontoinhaber autorisiert. Zugangsdaten, Session-Dateien, private Messberichte und Home-Assistant-Testkonten stehen nicht im Repository.

## Automatische Prüfungen

Parser: Einheiten, Komma/Punkt, Gruppierung, Rundungsauflösung, unparsebare/negative/mehrdeutige Werte. Ledger: Neustart, identische Retries, Tageswechsel mit Restenergie, Korrektur nach unten, begrenztes Nachholen, Lücken, verlorene Daten und Anlagenwechsel. Echtes Chromium: Session-Cookies, Ladezustände, HTTP-Fehler, Abschalten der Webseiten-Timer, Abbruch beim Shutdown, DOM-Discovery, Energie-Tooltips, identische Prozentlabels, Wechsel zurück zu Heute, Null-Produktion und Nennleistung gegenüber tatsächlicher PV-Leistung. Echter Mosquitto: Discovery, retained States, Feldgültigkeit, Wiederverbindung und Shutdown-Availability.

48 automatische Prüfungen bestanden im AMD64-Container. Die sechs zusätzlichen Prüfungen in 0.2.1 decken sichere Fehlerdiagnose, defekte/geschlossene Seiten, unterbrochene Navigation sowie Wiederholung trotz gleichzeitigem Navigations- und Idle-Fehler ab. Der normale Live-Abruf besteht weiterhin. GitHub Actions führt die Prüfungen mit lokalen/synthetischen Seiten und einem separaten Broker durch. Synthetische Testseiten sind nicht als echte SolarEdge-HTML-Samples zu verstehen.

## Live bestätigt

- AMD64-Container startet Chromium und lädt SolarEdge; Hauptprozess läuft als UID 1000.
- Regulärer Login mit frischem Browserkontext, anschließend private Session-Speicherung.
- Wiederverwendung gespeicherter Session ohne erneute Anmeldung.
- Eindeutige Auswahl der tatsächlichen Anlage und normaler Dashboard-Aufruf.
- Heute, Vortag, Vorvortag sowie Rückkehr zu Heute mit jeweiligen Energie-Tooltips.
- Auslesen von PV-/Verbrauchsleistung, Importfluss, Status, Aktualisierung und Temperatur aus sichtbarem DOM.
- Normale Scraper-Ausgabe wird über einen separaten Mosquitto an eine getrennte Home-Assistant-Container-Testinstanz übertragen.
- Home Assistant legt 18 Sensoren an und nimmt alle fünf kWh-Gesamtzähler als Energie-Summenstatistiken an.
- PV-Erzeugung, Netzbezug und Einspeisung wurden im Energie-Dashboard gespeichert; Home Assistants Energie-Validierung meldet keine Fehler.
- MQTT-Broker-Neustart: automatische Wiederverbindung mit erneuter Discovery und vorhandenen Werten, ohne neuen SolarEdge-Abruf.
- Nutzergerät mit Home Assistant auf x86-64: am 02.10.2026 bestätigen die bereitgestellten Logs unter 0.2.1 MQTT-Verbindung, Chromium-Start, regulären Login, private Session-Speicherung und einen vollständigen Dashboard-Abruf mit gespeichertem Energie-Ledger.

## Noch nicht bestätigt / Grenzen

- Nativer AArch64-Betrieb. ARM64-Build und Chromium-Download funktionieren; QEMU unter AMD64 ist kein belastbarer Chromium-Laufzeitnachweis.
- Mehrtägiger unbeaufsichtigter Dauerbetrieb und realer Mitternachtswechsel. Die Ledger-Logik ist automatisch geprüft; tatsächliche vergangene Tagesansichten wurden live ausgelesen.
- Andere Anlagen, Konto-Sprachen, Batterieanlagen und abweichende SolarEdge-Frontends. Vor produktivem Betrieb dort Discovery prüfen.
- MFA/CAPTCHA: Pausenlogik statt Umgehung; kein eingebauter interaktiver Webbrowser.
- Statistik beginnt bei Inbetriebnahme; MQTT importiert keine rückdatierten Statistiken.

## Ergänzungen in 0.3.0

- 13 zusätzliche Unit-Tests: Tagesbilanz/Quotienten, echte Nullwerte, fehlende Nenner, Alterung ohne neuen Abruf, Mitternachtsgültigkeit, Ledger-Übernahme, Ausfälle, späte Korrekturen, Kompaktierung sowie 23-/25-Stunden-Tage.
- 61 Prüfungen einschließlich echtem Chromium und isoliertem Mosquitto bestanden. Ein zusätzlicher opt-in Test verwendet echtes Home Assistant 2026.9.4: wiederholter Import ohne Doppelzählung, ursprüngliche Tageszuordnung, spätere Korrekturen ohne falsche Folgetage und erfolgreiche Energie-Dashboard-Validierung aller drei Quellen.
- Blueprint, Automation und beide Benachrichtigungsaktionen gegen HA-Schemas geprüft. Warnungs- und Erholungsvorlagen mit zehn Zustandskombinationen geprüft; es wurden keine Handy-Nachrichten versendet.
- Erweiterte Dashboard-Karten mit Beispieldaten im Browser geprüft, einschließlich hellem/dunklem Theme, schmaler Ansicht, fehlenden Werten und überaltertem Abruf. Keine Browserfehler.
- Ein erneuter realer SolarEdge-Abruf mit gespeicherter Session, neuen Tageswerten, MQTT und anschließendem Statistikimport in die getrennte HA-Testinstanz war erfolgreich.

Der Live-Importtest verwendet einen privaten HA-Testzugang direkt zum Test-Core. Die automatische Authentifizierung über den echten Supervisor-Proxy muss nach dem Update auf dem Nutzergerät bestätigt werden. Die Route und Berechtigung entsprechen der offiziellen HA-Dokumentation. Die Stundenverteilung nicht beobachteter Zeiträume bleibt unbekannt; der Import ordnet diese Mengen ausschließlich dem korrekten Tag zu.
