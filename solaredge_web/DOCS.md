# Einrichtung

SolarEdge-Login und exakten Anlagennamen eintragen, MQTT-Broker/Integration einrichten und mit `mode: normal` starten. Standard: ein Abruf alle 30 Minuten. Das Repository gehört in den Home-Assistant-Add-on-/App-Store, nicht HACS.

Für das Energie-Dashboard:

- PV: `sensor.solaredge_pv_energy_total`
- Netzbezug: `sensor.solaredge_grid_import_energy_total`
- Einspeisung: `sensor.solaredge_grid_export_energy_total`

Historie beginnt ab Inbetriebnahme. Fehlende Live-Flussrichtungen sind unavailable. Bei geänderter Oberfläche `mode: discovery` starten, private Berichte prüfen und zurück auf `normal` wechseln. Bei MFA/CAPTCHA pausiert das Add-on bis Neustart.

Konfiguration, Sensoren und Fehlersuche: [README](https://github.com/dr8ecker/solaredge_web/blob/main/solaredge_web/README.md).
