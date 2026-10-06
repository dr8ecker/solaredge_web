# Energiezähler

Die primären Datenquellen sind sichtbare SolarEdge-Tageswerte. Der Scraper stellt Tag/Heute ein, prüft Anfangs-/Enddatum, wartet auf Energie-DOM-Änderungen und liest PV-Erzeugung aus der Produktionskarte. Netzbezug, Einspeisung und PV-Eigenverbrauch stammen aus sichtbaren Hover-Tooltips. Die gerundeten Prozentanteile werden nicht multipliziert. Produktions-/Verbrauchskarten und Tooltip-Summen müssen innerhalb der angezeigten Rundungsauflösung zusammenpassen.

Eine Drei-Tages- oder Wochenansicht enthält überlappende Werte. Sie wird nicht zyklisch addiert. Der sichtbare Lebensdauer-PV-Wert ist bei dieser Anlage in MWh grob gerundet; er eignet sich nicht für genaue Zuwächse zwischen den Abrufen.

## Ledger und Tageswechsel

`/data/runtime/energy_ledger.json` speichert je Kalenderdatum den bisher höchsten gültigen Stand aller fünf Energiefelder. Gesamtzähler sind die Summe dieser Tage plus kompaktierte ältere Tage. Ein Retry oder Neustart kann denselben Tageswert nicht doppelt zählen. Das Ledger wird vor MQTT atomar gespeichert.

Beim ersten Abruf am neuen Tag wird der Vortag über die reguläre Zurück-Schaltfläche abgefragt. Damit werden Restenergie nach dem letzten Vortagsabruf und bereits vorhandene Energie des neuen Tags gemeinsam übernommen. Auch spätere Abrufe lesen den Vortag erneut, um verspätete Daten zu erfassen. Nach Ausfällen werden bis zu `history_days` Tage nachgeholt. Längere Lücken erscheinen in `energy_gap_count` und `last_scrape.json`; es werden keine fehlenden Werte erfunden.

Mit dem Standard `poll_interval: 900` ab 0.3.1 beginnen reguläre Abrufe bei :00:01, :15:01, :30:01 und :45:01 in der Anlagenzeitzone. Der Mitternachtsabruf beginnt um 00:00:01; Tageswerte bleiben bis zum erfolgreichen Auslesen unavailable. Die Null zum Tagesbeginn wird nicht vorweggenommen. Ein sofortiger Startabruf und Wiederholungen nach Fehlern können außerhalb dieser Termine liegen.

Sinkende Tagesstände werden als Rundung/Korrektur protokolliert; der vorherige Höchststand bleibt bestehen. Diese konservative Regel verhindert falsche Resets, übernimmt aber nachträgliche Abwärtskorrekturen nicht. Auflösung und Rundung der Webseite begrenzen die Genauigkeit. Unterschiedlich gerundete Zähler können leichte Bilanzabweichungen erzeugen.

Eine ausdrücklich angezeigte Null-Gesamtenergie beweist bei nichtnegativen Komponenten Null. Ein fehlender Tooltip oder ein gerundetes 100%-Label allein beweist keine Null.

Ab 0.3.10 darf ein fehlendes PV-Verbrauchslabel die ausdrücklich gelesene PV-Eigenverbrauchsmenge aus der Produktionskarte wiederverwenden, einschließlich ihrer Rundungsauflösung. Netzbezug wird weiterhin separat aus seinem Tooltip gelesen; beide Mengen müssen die Verbrauchssumme innerhalb der Rundungsauflösung ergeben. Unbekannte oder ungültige Tooltips werden nicht durch diese Wiederverwendung ersetzt. Deutsche und englische Beschriftungen werden parallel erkannt; typografische Leerzeichen und Bindestriche ändern nur den Labelvergleich, nicht die gelesenen Mengen.

## Home Assistant

Die dauerhaften kWh-Gesamtzähler werden als `device_class: energy`, `state_class: total` ohne `last_reset` veröffentlicht. Die reine Tagesanzeige hat keine Zähler-State-Class und ist nicht für das Energie-Dashboard gedacht. Diese Wahl folgt den [Home-Assistant-Sensorregeln](https://developers.home-assistant.io/docs/core/entity/sensor/#how-to-choose-state_class-and-last_reset).

Home Assistant verwendet die erste Statistik als Ausgangspunkt. Aufzeichnung beginnt mit Inbetriebnahme. MQTT-Nachholen schreibt die Energiedifferenz zum Zeitpunkt des aktuellen Abrufs, nicht rückwirkend in alte Stunden/Tage. Das Abrufintervall begrenzt die zeitliche Auflösung; auch feste Viertelstunden ändern diese Zuordnung von Ausfall- und Mitternachtsenergie nicht. Ab 0.3.0 bietet der separate Historienimport eigene **Tagesgenau**-Quellen: [HISTORY.md](HISTORY.md). Diese Quellen korrigieren die Tageszuordnung; die beschriebenen Einschränkungen der MQTT-Zähler bleiben bestehen.

## Datenverlust

Beschädigtes Ledger, geänderte Konto-/Anlagenidentität oder fehlendes Ledger bei vorhandenem Initialisierungsmarker führen zum Fehler statt zu Null. Die Backup-Datei ist keine automatische Rücksetzung: Ein älterer Stand würde negative Statistiken erzeugen. Sämtliches `/data` mit sichern. Bei vollständig gelöschtem `/data` kann frühere Initialisierung nicht erkannt werden; vor erneuter Verwendung eine konsistente Sicherung wiederherstellen.

## Stundenbeobachtungen und externe Statistikquellen

Das kompatibel erweiterte Ledger enthält optional `hours`: je Tag und UTC-Stundenbeginn die bis dahin bekannte Tagesenergie. Wiederholungen innerhalb einer Stunde ersetzen denselben Beobachtungspunkt. Alte Ledger ohne dieses Feld behalten ihre Tageswerte und Gesamtstände.

Der Import erzeugt für jede der fünf Energiemengen eine eigene `solaredge_web:`-Statistik mit kWh, `unit_class: energy`, `mean_type: 0` und einer kumulativen Summe. Ein Ausgangspunkt vor dem ersten gespeicherten Tag verhindert, dass dessen Energie als bloßer Startzähler verloren geht. Alle noch gespeicherten Tage werden bei jedem Import konsistent neu berechnet; spätere Tageskorrekturen ändern auch die Folgesummen. Die Import-API ersetzt gleiche Statistik-ID/Stundenbeginn-Kombinationen. Bestehende `sensor.*`-Statistiken werden nicht verändert.

Fehlende historische Stundenprofile und Restenergie abgeschlossener Tage werden in deren letzter Stunde verbucht. UTC-Stundeniteration berücksichtigt den 23- bzw. 25-Stunden-Tag in Europe/Berlin. Der Import bestätigt die zuletzt gespeicherten Summen durch Zurücklesen aus HA. Fehler bleiben separat sichtbar und verhindern keine MQTT-Veröffentlichung.

---

© 2026 [8ecker.de](https://8ecker.de)
