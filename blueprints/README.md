# SolarEdge-Ausfallmeldung aufs Handy

Voraussetzungen: Add-on ab **0.3.0** und ein Handy, das über die Home-Assistant-Companion-App in HA registriert ist. Das Importieren dieser Vorlage sendet noch keine Nachricht; die Automation wird erst durch deine Einrichtung aktiviert.

1. **Einstellungen → Automatisierungen & Szenen → Vorlagen/Blueprints → Vorlage importieren** öffnen.
2. Diese URL einfügen:

   `https://github.com/dr8ecker/solaredge_web/blob/main/blueprints/solaredge-outage.yaml`

3. Aus der Vorlage eine Automation erstellen und dein Handy auswählen.
4. Die beiden Sensoren **Datenzustand** und **Historienimport** prüfen. Falls HA ihren IDs einen Suffix angehängt hat, die tatsächlichen Sensoren im Auswahlfeld einstellen.
5. Speichern. Die zusätzliche Fehlerwartezeit beträgt standardmäßig fünf Minuten; eine Entwarnung ist voreingestellt.

Die Vorlage meldet länger anhaltende Abruffehler, zu alte Daten, erforderliche Anmeldung, ein nicht erreichbares Add-on/MQTT sowie Fehler beim Historienimport. Einzelne nicht angezeigte Netzrichtungen und eine reguläre PV-Leistung von null lösen keine Meldung aus.

Der Sensor **Datenzustand** wird vom laufenden Add-on spätestens alle zehn Sekunden überprüft. Seine Altersschwelle beträgt mindestens 15 Minuten bzw. drei Abrufintervalle, je nachdem, welcher Wert größer ist. Mit dem Standard ab 0.3.1 (`poll_interval: 900`, alle 15 Minuten) sind das **45 Minuten**. Bestehende Installationen behalten ihre gespeicherte Einstellung: Bei `1800` sind es weiterhin 90 Minuten, bis du das Intervall auf `900` änderst und das Add-on neu startest. Die zusätzliche Wartezeit der Automation verhindert Meldungen bei kurzen Neustarts.

Pro anhaltendem Vorfall sendet die laufende Automation eine Warnung und wartet auf erfolgreiche Erholung. Erst dann kann ein neuer Vorfall eine neue Warnung auslösen. Eine Entwarnung ersetzt auf unterstützten Handys die vorherige Meldung. Nach einem HA-Neustart oder dem Neuladen der Automationen beginnt die Wartezeit neu; ein weiterhin bestehender Vorfall kann dann erneut gemeldet werden.

Wenn du keinen Zugriff auf ein Handy mit Companion-App hast, kannst du dieselben Zustände in einer eigenen HA-Automation für eine andere Benachrichtigungsaktion verwenden.
