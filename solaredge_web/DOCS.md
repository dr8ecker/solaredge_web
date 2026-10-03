# Einrichtung

SolarEdge-Login und exakten Anlagennamen eintragen, MQTT-Broker/Integration einrichten und mit `mode: normal` starten. Ab 0.3.1 ist der Standard `poll_interval: 900`: Abruf zu **:00:01, :15:01, :30:01 und :45:01**, einschließlich **00:00:01** in der Anlagenzeitzone. Beim Start wird sofort abgerufen; bei Fehlern gelten die üblichen Wiederholungs- und Schutzpausen. Das Repository gehört in den Home-Assistant-Add-on-/App-Store, nicht HACS.

**Nach einem Update bleiben gespeicherte Optionen erhalten.** Steht `poll_interval` noch auf `1800`, für den Viertelstundentakt auf **900** ändern und das Add-on neu starten. Die neuen Werte erscheinen nach Abschluss des Abrufs, auch nach Mitternacht. Bis dahin bleiben Tageswerte unavailable; es werden keine Nullen erfunden.

Für das Energie-Dashboard nach erfolgreichem Historienimport die drei Statistiken **SolarEdge PV-Erzeugung · Tagesgenau**, **SolarEdge Netzbezug · Tagesgenau** und **SolarEdge Einspeisung · Tagesgenau** auswählen. Bestehende Quellen ersetzen. [Umstellungsanleitung](https://github.com/dr8ecker/solaredge_web/blob/main/solaredge_web/HISTORY.md).

Tagesbilanz, Autarkie und Eigenverbrauchsquote stehen als zusätzliche Sensoren bereit. Nachgeholte Tagesenergie wird dem Ursprungstag zugeordnet; eine genaue vergangene Stundenverteilung ist nicht bekannt. Fehlende Live-Flussrichtungen bleiben unavailable.

[Dashboard-Karten](https://github.com/dr8ecker/solaredge_web/blob/main/dashboard/README.md) und [optionale Ausfallmeldung aufs Handy](https://github.com/dr8ecker/solaredge_web/blob/main/blueprints/README.md).

Bei geänderter Oberfläche `mode: discovery` starten, private Berichte prüfen und zurück auf `normal` wechseln. Bei MFA/CAPTCHA pausiert das Add-on bis Neustart.

Konfiguration, Sensoren und Fehlersuche: [README](https://github.com/dr8ecker/solaredge_web/blob/main/solaredge_web/README.md).
