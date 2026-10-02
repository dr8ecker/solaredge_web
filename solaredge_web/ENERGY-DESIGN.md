# Energiezähler

Die primären Datenquellen sind sichtbare SolarEdge-Tageswerte. Der Scraper stellt Tag/Heute ein, prüft Anfangs-/Enddatum, wartet auf Energie-DOM-Änderungen und liest PV-Erzeugung aus der Produktionskarte. Netzbezug, Einspeisung und PV-Eigenverbrauch stammen aus sichtbaren Hover-Tooltips. Die gerundeten Prozentanteile werden nicht multipliziert. Produktions-/Verbrauchskarten und Tooltip-Summen müssen innerhalb der angezeigten Rundungsauflösung zusammenpassen.

Eine Drei-Tages- oder Wochenansicht enthält überlappende Werte. Sie wird nicht zyklisch addiert. Der sichtbare Lebensdauer-PV-Wert ist bei dieser Anlage in MWh grob gerundet; er eignet sich nicht für genaue 30-Minuten-Zuwächse.

## Ledger und Tageswechsel

`/data/runtime/energy_ledger.json` speichert je Kalenderdatum den bisher höchsten gültigen Stand aller fünf Energiefelder. Gesamtzähler sind die Summe dieser Tage plus kompaktierte ältere Tage. Ein Retry oder Neustart kann denselben Tageswert nicht doppelt zählen. Das Ledger wird vor MQTT atomar gespeichert.

Beim ersten Abruf am neuen Tag wird der Vortag über die reguläre Zurück-Schaltfläche abgefragt. Damit werden Restenergie nach dem letzten Vortagsabruf und bereits vorhandene Energie des neuen Tags gemeinsam übernommen. Auch spätere Abrufe lesen den Vortag erneut, um verspätete Daten zu erfassen. Nach Ausfällen werden bis zu `history_days` Tage nachgeholt. Längere Lücken erscheinen in `energy_gap_count` und `last_scrape.json`; es werden keine fehlenden Werte erfunden.

Sinkende Tagesstände werden als Rundung/Korrektur protokolliert; der vorherige Höchststand bleibt bestehen. Diese konservative Regel verhindert falsche Resets, übernimmt aber nachträgliche Abwärtskorrekturen nicht. Auflösung und Rundung der Webseite begrenzen die Genauigkeit. Unterschiedlich gerundete Zähler können leichte Bilanzabweichungen erzeugen.

Eine ausdrücklich angezeigte Null-Gesamtenergie beweist bei nichtnegativen Komponenten Null. Ein fehlender Tooltip oder ein gerundetes 100%-Label allein beweist keine Null.

## Home Assistant

Die dauerhaften kWh-Gesamtzähler werden als `device_class: energy`, `state_class: total` ohne `last_reset` veröffentlicht. Die reine Tagesanzeige hat keine Zähler-State-Class und ist nicht für das Energie-Dashboard gedacht. Diese Wahl folgt den [Home-Assistant-Sensorregeln](https://developers.home-assistant.io/docs/core/entity/sensor/#how-to-choose-state_class-and-last_reset).

Home Assistant verwendet die erste Statistik als Ausgangspunkt. Aufzeichnung beginnt mit Inbetriebnahme. MQTT-Nachholen schreibt die Energiedifferenz zum Zeitpunkt des aktuellen Abrufs, nicht rückwirkend in alte Stunden/Tage. 30 Minuten sind für Summen brauchbar; Zeitauflösung und Zuordnung von Ausfall-/Mitternachtsenergie sind entsprechend gröber. Ein rückdatierter Historienimport wäre eine separate Erweiterung.

## Datenverlust

Beschädigtes Ledger, geänderte Konto-/Anlagenidentität oder fehlendes Ledger bei vorhandenem Initialisierungsmarker führen zum Fehler statt zu Null. Die Backup-Datei ist keine automatische Rücksetzung: Ein älterer Stand würde negative Statistiken erzeugen. Sämtliches `/data` mit sichern. Bei vollständig gelöschtem `/data` kann frühere Initialisierung nicht erkannt werden; vor erneuter Verwendung eine konsistente Sicherung wiederherstellen.
