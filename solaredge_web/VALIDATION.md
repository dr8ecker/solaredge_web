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

## Ergänzungen in 0.3.1

- Standardintervall 900 Sekunden; 11 zusätzliche Tests für feste Viertelstunden, 00:00:01, exakte Grenzen, lange Abrufe ohne Zeitverschiebung oder Warteschlange, angepasste Intervalle, Sommer-/Winterzeit sowie Uhrkorrekturen und sofortigen Abbruch.
- 72 Prüfungen einschließlich echtem Chromium und isoliertem Mosquitto im gebauten 0.3.1-Image bestanden. Der zusätzliche Test gegen echtes Home Assistant ist weiterhin Teil des CI-Laufs.
- Transparente Übersicht und Detailkarte im Browser geprüft: Hintergrund, Schatten und Glasfilter entfernt; runde Konturen an Messwertkacheln, transparente Symbole und Chips, Diagramm ohne Flächenfüllung. Helles/dunkles Theme, schmale Ansicht und ein Glas-Theme mit ausdrücklich priorisierten Hintergrundregeln geprüft; keine Browserfehler.
- Die Detailkarte verwendet ebenfalls `mod-card`, damit die Formatierung schon beim ersten direkten Öffnen zuverlässig angewendet wird. Der Kartenhintergrund wurde als vollständig transparent und die Rundung als 24 px bestätigt.

Der Viertelstundentakt bezeichnet die regulären Starts nach einem erfolgreichen Abruf. Beim Start erfolgt sofort ein Abruf; Fehler, Schutzpausen, lange laufende Abrufe oder größere Uhrkorrekturen können einzelne Termine auslassen. Tageswerte erscheinen nach erfolgreichem Auslesen der Webseite und werden auch kurz nach Mitternacht nicht durch erfundene Nullwerte ersetzt. Vorhandene Optionen werden nicht überschrieben; für vier reguläre Abrufe pro Stunde muss `poll_interval` auf `900` stehen.

## Ergänzungen in 0.3.3

- Vier zusätzliche Browser-Tests für bestätigte Import-/Export-Richtung mit 0 W in der Gegenrichtung, Richtungswechsel, deutsche/englische Labels, unbekannte/negative/falsche Einheiten, doppelte oder unvollständige Labels, versteckte Texte und explizit angezeigte Nullwerte.
- 76 Prüfungen mit echtem Chromium und isoliertem Mosquitto bestanden; der zusätzliche opt-in Test gegen echtes Home Assistant läuft in CI. MQTT bestätigt die Veröffentlichung einer gültigen Null und deren Ungültigkeit bei anschließend fehlender Flussrichtung.
- Am 03.10.2026 mit dem autorisierten Testkonto erneut live bestätigt: Bei eindeutig angezeigter positiver Einspeisung liefert der Scraper 0 W Netzbezug, ohne Warnungen. Dieser Browsercheck verwendet lokales Microsoft Edge mit Playwright; die automatischen DOM-Prüfungen verwenden Chromium im AMD64-Container. Der private Messbericht wird nicht veröffentlicht.

Die Gegenrichtung wird nur bei genau einem eindeutig beschrifteten, gültigen positiven Netzfluss ergänzt. Ohne bestätigte Richtung, bei unlesbaren/mehrdeutigen Angaben oder bei allein angezeigten 0 W wird keine fehlende Gegenrichtung geraten. Tagesenergie, Zähler und Statistikimport bleiben unverändert.

## Ergänzungen in 0.3.4

- Am 04.10.2026 unter Windows mit Playwright 1.63.0 und dessen Chromium gegen lokale Testseiten geprüft: 82 Tests ausgeführt, 80 bestanden. Zwei opt-in Prüfungen für einen separaten MQTT-Broker und eine separate Home-Assistant-Instanz wurden mangels Testdiensten übersprungen.
- Fünf zusätzliche Regressionstests prüfen Monitoring-Timeout, Netzwerkfehler beim Öffnen des Loginformulars, Formularlade-Timeout und Ausfüllfehler ohne Login-Schutzpause sowie einen unklaren Absendeversuch mit beibehaltener Schutzpause. Nach Fehlern vor dem Absenden gelingt der erneute Login; bei unklarem Absenden wird kein zweiter Klick versucht.
- Die bereitgestellten Betriebslogs zeigen `ERR_NETWORK_CHANGED` und Timeouts in `monitoring_ui_wait`. Deren Ursache und die Korrektur auf dem Home-Assistant-Gerät wurden noch nicht live geprüft. Ein Monitoring-Timeout allein aktiviert auch im bisherigen Code keine Login-Schutzpause; die behobene vorzeitige Aktivierung betrifft die anschließende Login-Vorbereitung.

## Ergänzungen in 0.3.5

- Am 04.10.2026 unter Windows mit Playwright und lokalem Chromium erneut 82 Tests ausgeführt: 80 bestanden, zwei opt-in Prüfungen für einen separaten MQTT-Broker und eine separate Home-Assistant-Instanz übersprungen.
- Versionsangaben, Manifest, Python-Standard und beide Konfigurationsbeispiele geprüft: Version 0.3.5 und Standard-Timeout 60000 Millisekunden. Ein explizit gespeicherter Timeout von 30000 Millisekunden bleibt erhalten.
- Die bereitgestellten Logs aus 0.3.4 bestätigen Wiederholungen nach `login_form_wait`-Timeouts ohne vorzeitige Login-Schutzpause. Ob 60 Sekunden Wartezeit das Laden des echten Loginformulars ermöglichen, muss auf dem Home-Assistant-Gerät getestet werden.

---

© 2026 [8ecker.de](https://8ecker.de)
