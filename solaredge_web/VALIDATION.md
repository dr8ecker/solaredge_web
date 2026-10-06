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

## Ergänzungen in 0.3.6

- Am 04.10.2026 sieben neue Browser-Regressionstests ergänzt: normaler Login über den Standard-Einstieg, direkte SSO-Rückkehr ohne Formular, verzögertes Session-Rendering, Sicherheitsabfrage am Loginziel, versteckte Sitzungsindikatoren, Sitzungsmerkmale auf fremdem Host und ausschließlich feste Diagnosewerte ohne private Inhalte.
- Fünf dieser Ablauffehler wurden zunächst gegen den unveränderten 0.3.5-Code reproduziert. Mit der Korrektur bestehen alle 16 Loginbrowser-Tests. Im AMD64-Container bestehen insgesamt 88 Tests einschließlich echtem Chromium und separatem Mosquitto; der zusätzliche Test gegen eine separate Home-Assistant-Instanz wurde lokal übersprungen und bleibt Teil der CI-Prüfung.
- Die öffentliche SolarEdge-Seite wurde im Docker-Container mit frischem Browserkontext geprüft: Der Standard-Einstieg erreicht das erwartete englische Loginformular. Der aktuelle Ablauf wurde vor dem Ausfüllen gestoppt; es wurden keine Zugangsdaten übermittelt. Der 0.3.6-Container wurde erfolgreich gebaut.
- Ob eine direkte Rückleitung mit gespeicherter Sitzung die Timeouts auf dem Nutzergerät verursacht, ist noch nicht bestätigt. Die bereitgestellten Logs aus 0.3.5 belegen nur das weiterhin fehlende erkannte Loginformular nach 60 Sekunden. Zusätzliche Zustandsdiagnosen sollen abweichende Ursachen beim nächsten Gerätetest unterscheiden.

## Ergänzungen in 0.3.7

- Die Nutzerlogs aus 0.3.6 zeigen ein sichtbares Passwortfeld und zwei Formulare auf `solaredge_login`, während das exakte E-Mail-Label nicht erkannt wird. Das grenzt den aktuellen Fehler auf die Formularerkennung ein; eine erfolgreiche SSO-Rückkehr ist in diesem Versuch nicht zu sehen.
- Fünf neue Regressionstests für deutsche Labels, ein ungelabeltes E-Mail-Feld neben dem Firmen-/SSO-Formular, `autocomplete="username"` und mehrdeutige Felder/Formulare schlagen mit dem unveränderten 0.3.6-Code fehl. Mit der Korrektur bestehen alle 21 Loginbrowser-Tests. Mehrdeutige Fälle werden vor jeder Eingabe und Übermittlung abgewiesen.
- Am 04.10.2026 bestehen im gebauten 0.3.7-AMD64-Container 93 Tests einschließlich echtem Chromium und isoliertem Mosquitto. Ein zusätzlicher Test gegen eine separate Home-Assistant-Instanz wurde lokal übersprungen und bleibt Teil der CI-Prüfung.
- Die öffentliche SolarEdge-Seite wurde im Docker erneut geprüft: Im normalen Passwortformular sind `type=email`, `name=username`, `type=password` und eine Submit-Aktion vorhanden; das zweite Formular enthält das Firmen-E-Mail-Feld. Der neue Ablauf erkennt eindeutig das normale Formular und wurde vor dem Ausfüllen gestoppt. Es wurden keine echten Zugangsdaten übermittelt. Die Bestätigung auf dem Nutzergerät steht noch aus.

## Ergänzungen in 0.3.8

- Am 05.10.2026 unter Windows mit Playwright und lokalem Chromium 100 Tests ausgeführt: 98 bestanden. Zwei opt-in Prüfungen für einen separaten MQTT-Broker und eine separate Home-Assistant-Instanz wurden mangels Testdiensten übersprungen.
- Sechs neue Regressionstests prüfen feste Diagnosegründe ohne private Meldungsinhalte, fehlende gegenüber mehrdeutigen/ungültigen Mengen, das betroffene Verteilungs- und Tooltipfeld, die Sicherung des fehlgeschlagenen DOM vor dem Entladen ohne Energieveröffentlichung sowie Wiederholungen und begrenzte Berichtserfassung bei einem fehlgeschlagenen Diagnoseversuch.
- Die bereitgestellten 0.3.7-Gerätelogs bestätigen akzeptierte Sitzung und wiederholte `ParseError`-Fehler in `dashboard_scrape`, ohne gemeldeten Browserabsturz oder OOM-Kill. Die ursprüngliche Parsermeldung und betroffene Energieansicht fehlen. Die tatsächliche Geräteursache wurde weder reproduziert noch behoben; die Änderung macht den nächsten Fehler unterscheidbar und bewahrt dessen sichtbare DOM-Daten privat.
- Der aktuelle Docker-Dienst ist lokal nicht verfügbar. Diese Änderung wurde weder im Add-on-Container noch gegen die echte SolarEdge-Anlage oder das Nutzergerät geprüft.

## Ergänzungen in 0.3.9

- Am 06.10.2026 zeigen die bereitgestellten Screenshots die englischen Legenden `From Solar` und `To Building` sowie die Leistungsrichtung `Exporting`. Diese Beschriftungen fehlten in den bisherigen Keywords. Die Screenshots enthalten keine geöffneten Energie-Tooltips; deren DOM und genaue kWh-Werte wurden damit nicht live verifiziert.
- Zwei neue Tests mit synthetischem DOM und expliziten Tooltip-Mengen schlagen gegen den unveränderten 0.3.8-Code fehl. Der isolierte `From Solar`-Test reproduziert `distribution_energy_incomplete` in der Verbrauchskarte; die vollständig englische Verteilung scheitert zusätzlich an `To Building`. Beide bestehen mit der Korrektur. Der vorhandene Browser-Richtungswechseltest prüft zusätzlich `Exporting` und `Importing`.
- Unter Windows mit Playwright und lokalem Chromium 102 Tests ausgeführt: 100 bestanden. Zwei opt-in Prüfungen für separate MQTT- und Home-Assistant-Testdienste wurden übersprungen. Die Bestätigung der Korrektur auf dem Nutzergerät steht noch aus.

## Ergänzungen in 0.3.10

- Die am 06.10.2026 bereitgestellten vier deutschen Tooltip-Screenshots zeigen `Ins Netz`, `Ins Gebäude`, `Vom Netz` und `Aus PV-Energie`. Ein synthetischer Browser-Test mit genau diesen sichtbaren Texten und Mengen besteht bereits gegen 0.3.9: 46 kWh Produktion, 41.1 kWh Einspeisung, 4.85 kWh Eigenverbrauch, 7.34 kWh Verbrauch und 2.5 kWh Netzbezug. Die Rundungsdifferenzen liegen innerhalb der bisherigen Prüfgrenzen. Ein Screenshot beweist weder die Unicode-Zeichen noch die DOM-Struktur der Add-on-Seite; die verbleibende Geräteursache ist nicht bestätigt.
- Fünf neue Browser-Tests prüfen die Screenshot-Mengen, den übernommenen ausdrücklich gelesenen PV-Eigenverbrauch bei fehlendem zweitem Label, unverändert abgewiesene widersprüchliche Verbrauchssummen und unbekannte Tooltips sowie deutsche/englische Labels mit geschützten Leerzeichen und Bindestrichvarianten. Der Test mit fehlendem positivem PV-Verbrauchslabel scheitert zunächst gegen 0.3.9 und besteht mit der Korrektur. Der Typografietest verwendet absichtlich widersprüchliche Tooltip-Mengen und prüft deren Ablehnung, damit ein unerkanntes Label nicht durch einen Ersatzwert verdeckt werden kann.
- Unter Windows mit Playwright und lokalem Chromium 107 Tests ausgeführt: 105 bestanden, zwei Prüfungen für separate MQTT- und Home-Assistant-Testdienste übersprungen. Fehlende Felder erscheinen ausschließlich als feste Feldnamen in der Diagnose. Die Bestätigung auf dem Nutzergerät steht noch aus.

## Ergänzungen in 0.3.11

- Die neuen Nutzerlogs nennen `missing_fields: ['grid_import_energy']`. Die Tooltip-Screenshots zeigen zuvor vorhandenen Netzbezug mit `Vom Netz: 2.5 kWh`. Die Sprache allein erklärt den aktuellen Fehler nicht. Die Standardansicht des Add-on-Browsers ist 1440 Pixel breit, der bereitgestellte vollständige Dashboard-Screenshot etwa 1770 Pixel. Eine responsive Unterdrückung der schmalen Prozentbeschriftung ist damit eine plausible, noch nicht auf dem Gerät bestätigte Ursache.
- Vier neue Browser-Tests prüfen einen bei 1440 Pixel ausgelassenen Importtext mit erfolgreichem echten Tooltip-Lesen bei 1920 Pixel, per CSS versteckte Labels, weiterhin fehlenden Import nach der einmaligen Erweiterung sowie nicht erkannte Importtexte ohne Erweiterung. Der Test mit responsiv ausgelassenem Label reproduziert gegen 0.3.10 `distribution_energy_incomplete` mit fehlendem Netzbezug und besteht mit der Korrektur. Die synthetischen Testseiten sind kein Beleg für die private SolarEdge-DOM-Struktur.
- Unter Windows mit Playwright und lokalem Chromium 111 Tests ausgeführt: 109 bestanden, zwei Prüfungen für separate MQTT- und Home-Assistant-Testdienste übersprungen. Nach Ergänzung der Tooltip-Schließprüfung bestehen die zwei Layout-Wiederholungstests erneut. Die Gerätebestätigung steht noch aus.

---

© 2026 [8ecker.de](https://8ecker.de)
