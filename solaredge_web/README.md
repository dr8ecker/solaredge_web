# SolarEdge Web Scraper 0.3.8

Das Add-on bringt die Werte deiner PV-Anlage aus dem SolarEdge-Monitoring-Portal nach Home Assistant. Damit kannst du Solarerzeugung, Hausverbrauch, Netzbezug und Einspeisung im Energie-Dashboard auswerten und die wichtigsten Werte auf deinem normalen Dashboard anzeigen.

## So funktioniert es

Ein integrierter Browser öffnet die SolarEdge-Webseite, meldet sich mit deinem regulären Konto an und wählt deine Anlage. Das Add-on liest die angezeigten Leistungs- und Energiewerte aus. Dafür brauchst du keinen SolarEdge-API-Schlüssel und keinen Modbus-Zugang zum Wechselrichter.

Die Werte gelangen über MQTT nach Home Assistant. Die Sensoren werden automatisch angelegt. Das Add-on speichert die Energietage dauerhaft und importiert sie zusätzlich in eigene HA-Statistikquellen. Nach einem Ausfall nachgeholte Tagesmengen bleiben dadurch ihrem ursprünglichen Kalendertag zugeordnet.

Beim Start erfolgt sofort ein Abruf. Mit dem Standardintervall von 15 Minuten folgen Abrufe zu **:00:01, :15:01, :30:01 und :45:01**, auch um **00:00:01** in der Anlagenzeitzone. Zwischen den Abrufen wird die Webseite entladen, damit ihre Hintergrundaktualisierungen keine zusätzliche Last erzeugen. Eine gespeicherte Anmeldung wird wiederverwendet.

## Wofür ist es gedacht?

- **Energie-Dashboard:** Erzeugung, Netzbezug und Einspeisung über Tage, Wochen und Monate verfolgen.
- **PV-Übersicht:** Tagesbilanz, Eigenverbrauch und Autarkie sowie die Leistung beim letzten Abruf anzeigen.
- **Ausfälle erkennen:** Datenalter und Abruffehler sichtbar machen; auf Wunsch eine Handy-Benachrichtigung einrichten.

## Was brauchst du?

Home Assistant mit App-/Add-on-Support, eine eingerichtete MQTT-Integration mit Broker, Internetzugang und ein SolarEdge-Konto mit Zugriff auf deine Anlage. Das Add-on wird über den **Home-Assistant-App-Store** installiert. Die optionalen Dashboard-Vorlagen verwenden Mushroom, mini-graph-card und card-mod aus HACS.

## Was bedeuten die Werte?

Leistungswerte sind Momentaufnahmen des jeweiligen Abrufs. Bei eindeutig angezeigtem Netzbezug oder Einspeisung mit positiver Leistung erhält die nicht angezeigte Gegenrichtung 0 W. Unklare oder nicht lesbare Flussangaben bleiben nicht verfügbar. Die Tagesbilanz verwendet die auf der Webseite angezeigten Energiemengen. Die genaue Stundenverteilung eines nachträglich gelesenen Tages lässt sich aus dessen Tagesmenge nicht rekonstruieren.

## Einrichtung und Hilfe

Die [Dokumentation](https://github.com/dr8ecker/solaredge_web/blob/main/solaredge_web/DOCS.md) enthält die Einrichtung, alle Optionen, die Sensorliste, das Energie-Dashboard, Fehlersuche und Sicherungen.

[Dashboard-Vorlagen](https://github.com/dr8ecker/solaredge_web/blob/main/dashboard/README.md) · [Prüfungen und bekannte Grenzen](https://github.com/dr8ecker/solaredge_web/blob/main/solaredge_web/VALIDATION.md)

---

© 2026 [8ecker.de](https://8ecker.de)
