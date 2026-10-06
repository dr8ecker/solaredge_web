# Changelog

## 0.3.11

- Bei fehlenden Verteilungslabels wird dieselbe Tagesansicht einmal auf 1920 Pixel verbreitert und vollständig erneut ausgelesen. Dadurch können in schmalen Balken ausgeblendete Prozentlabels und ihre echten Energie-Tooltips zugänglich werden. Es gibt keine zusätzliche Navigation und keine Berechnung fehlender Netzwerte aus Prozentanteilen.
- Nur sichtbare Prozentlabels werden zum Hover verwendet. Nicht erkannte Tooltiptexte, falsche Datumsbereiche und widersprüchliche Energiebilanzen lösen keine Layout-Wiederholung aus. Auch nach der breiteren Wiederholung fehlende Mengen bleiben Fehler.
- Die Fehlerdiagnose nennt zusätzlich `distribution_label_count` und `unrecognized_tooltip_count`, um fehlende Beschriftungen von nicht erkannten Texten zu unterscheiden. Deutsch und Englisch werden weiterhin gleichzeitig erkannt.
- Die Nutzerlogs aus 0.3.10 belegen fehlenden Netzbezug; die Ursache auf dem Gerät ist noch nicht bestätigt. Ein schmaler Browser gegenüber dem bereitgestellten Screenshot ist eine plausible Layoutursache, die mit lokalen responsiven Browser-Testseiten reproduziert wurde.

## 0.3.10

- Deutsche und englische Energie-Beschriftungen werden parallel erkannt; geschützte Leerzeichen, Unicode-Zeichenformen und Bindestrichvarianten werden für den Labelvergleich vereinheitlicht. Messwerte werden weiterhin aus den ursprünglichen Tooltip-Texten gelesen.
- Bei einem fehlenden PV-Verbrauchslabel kann der bereits ausdrücklich gelesene PV-Eigenverbrauch aus der Produktionskarte verwendet werden. Netzbezug muss weiterhin ausdrücklich gelesen werden und zur Verbrauchssumme passen. Unbekannte oder ungültige Tooltips und widersprüchliche Summen bleiben Fehler; fehlende Werte werden nicht aus Prozentanteilen berechnet.
- Unvollständige Verteilungen nennen mit `missing_fields` die tatsächlich fehlenden Energiefelder. Ein Wechsel des fehlenden Felds erzeugt einen neuen privaten Fehlerbericht.
- Die deutschen Screenshot-Texte und Mengen wurden bereits mit 0.3.9 korrekt gelesen. Die genaue Ursache des verbleibenden Gerätefehlers ist damit noch nicht bestätigt.

## 0.3.9

- Englische Energie-Beschriftungen `From Solar` und `To Building` werden als PV-Eigenverbrauch erkannt. Ein gelesener `From Solar`-Tooltip lässt die Verbrauchsaufteilung damit nicht mehr als unvollständig scheitern.
- Englische Leistungsrichtungen `Exporting` und `Importing` werden erkannt. Die sichtbaren kWh-/W-Werte und die vorhandenen Bilanzprüfungen bleiben maßgeblich; gerundete Prozentanteile werden nicht zur Berechnung verwendet.
- Zwei neue Browser-Regressionstests für den isolierten `From Solar`-Fehler und die vollständige englische Energieaufteilung; vorhandener Richtungswechseltest um `Exporting`/`Importing` erweitert.

## 0.3.8

- Dashboard-Validierungsfehler nennen einen festen Fehlergrund und bei Parserfehlern das betroffene Energiefeld. Fehlende und mehrdeutige Mengen, fehlende Verteilungslabels, unvollständige Teilmengen und abweichende Energiebilanzen sind dadurch unterscheidbar.
- Bei einem Validierungsfehler wird die aktuelle sichtbare Dashboardansicht automatisch als bereinigter privater Bericht gesichert, bevor der Browser die Seite entlädt. Pro Fehlergrund und Feld wird bis zum nächsten erfolgreichen Abruf nur ein Bericht gespeichert; Diagnosefehler beenden die Wiederholungen nicht.
- Die Ursache der am 05.10.2026 gemeldeten wiederholten `ParseError`-Fehler ist mit den bisherigen Logs noch nicht bestimmt. Diese Änderung verbessert die Diagnose und ist keine bestätigte Behebung des Gerätefehlers.

## 0.3.7

- Loginfelder werden innerhalb des eindeutigen sichtbaren Passwortformulars anhand von Feldtyp, Benutzername-Merkmalen oder deutschen/englischen Beschriftungen erkannt. Das exakte englische Label „Email address“ ist nicht mehr erforderlich.
- Das separate Firmen-/SSO-Formular wird nicht mit dem normalen Passwort-Login verwechselt. Bei mehrdeutigen Feldern, Formularen oder Absendeaktionen werden keine Zugangsdaten eingetragen.
- Login-Diagnose um Anzahl der Passwortformulare, passende Benutzerfelder und Formularbereitschaft erweitert.

## 0.3.6

- Nach „Anmelden“ wird eine direkte Rückkehr zur Anlagenübersicht oder zum Dashboard mit bestehender Sitzung erkannt. Das Add-on wartet dann nicht mehr vergeblich auf ein Loginformular.
- Verzögert erscheinende Sitzungen und sichtbare Sicherheitsabfragen werden bereits während des Login-Seitenwechsels erkannt. Versteckte Elemente oder Anlagen-Texte auf fremden Hosts bestätigen keine Anmeldung.
- Bei einem Login-Timeout zeigen zusätzliche Diagnoseangaben die Seitenkategorie und sichtbare Formular-/Sitzungsmerkmale, ohne URLs, Seitentexte, Eingabewerte oder Zugangsdaten zu protokollieren.

## 0.3.5

- Standard für Browseraktionen auf 60 Sekunden erhöht (`page_timeout: 60000`), um langsames Laden der Monitoring- und Loginoberfläche testen zu können.
- Bestehende Add-on-Optionen bleiben erhalten. Für den Test einen gespeicherten Wert von `page_timeout: 30000` auf `60000` ändern und neu starten.
- Die längere Wartezeit ist ein Diagnoseschritt für `login_form_wait`-Timeouts; eine Behebung auf dem Home-Assistant-Gerät ist noch nicht bestätigt.

## 0.3.4

- Login-Schutzpause beginnt erst vor dem Absenden des ausgefüllten Formulars. Navigations-, Formularlade- und Ausfüllfehler blockieren dadurch keine normalen Wiederholungen ohne Anmeldeversuch.
- Unklarer Absendeversuch behält die Schutzpause; bestätigte Fehlanmeldungen werden weiterhin nicht schnell wiederholt.
- Separate Login-Phasen für sichere Fehlerdiagnose und Regressionstests mit lokalem Browser ergänzt.

## 0.3.3

- Bei eindeutig erkanntem positivem Import-/Exportfluss wird die nicht angezeigte Gegenrichtung als 0 W veröffentlicht. Netzbezug bleibt beim Einspeisen dadurch verfügbar und umgekehrt.
- Fehlende, unlesbare, negative oder mehrdeutige Flussangaben ergeben weiterhin keine erfundenen Nullwerte. Versteckte SVG-Beschriftungen werden ignoriert.
- Browser- und MQTT-Prüfungen für Richtungswechsel, bestätigte Nullwerte sowie fehlerhafte und mehrdeutige Anzeigen ergänzt.

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
