# ISDT NXHOST Battery Monitor für macOS

Lokales Python-Web-Dashboard für experimentell dekodierte NXHOST-Messframes. Es
fragt die konfigurierten Kanäle **nacheinander** ab, speichert den Verlauf in
SQLite, zeigt Rohdaten und Fehler an und exportiert alle gespeicherten Messungen
als CSV.

> **Wichtiger Status:** Alle Feldzuordnungen und Einheiten sind experimentell.
> Die Deutung von Strom, Widerstand und Temperatur ist ausdrücklich **nicht
> verifiziert**. Dieses Projekt wurde mit gespeicherten Hex-Frames und
> automatisierten Tests geprüft, aber nicht an echter ISDT-Hardware getestet.

## Schnellstart

Voraussetzung: Dein vorhandenes `~/isdt-env` mit installiertem `isdttool`.

1. Das ZIP entpacken.
2. Im entpackten Ordner `start.command` doppelklicken.
3. Falls macOS nachfragt, das lokale Skript bestätigen. Alternativ im Terminal:

   ```bash
   cd ~/Downloads/isdt-nxhost-monitor
   ~/isdt-env/bin/python main.py
   ```

4. Der Browser öffnet `http://127.0.0.1:8765/`.
5. Mit `Ctrl+C` im Terminal beenden.

Die Datei `isdt_monitor/web/index.html` bitte **nicht direkt öffnen**. Eine
`file://`-Seite kann den Python-Server und damit weder USB-Abfragen noch Verlauf
oder CSV erreichen. Falls sie versehentlich geöffnet wird, zeigt sie lediglich
eine Startanweisung an.

Falls `start.command` nach dem Entpacken nicht ausführbar ist:

```bash
chmod +x ~/Downloads/isdt-nxhost-monitor/start.command
```

Das Dashboard ist ausschließlich über den lokalen Rechner erreichbar. Der
Server bindet fest an `127.0.0.1`, nicht an das WLAN/LAN.

## Ohne Hardware ansehen

Der Demo-Modus spielt nur die gespeicherten Gesprächsframes ab:

```bash
cd ~/Downloads/isdt-nxhost-monitor
~/isdt-env/bin/python main.py --demo
```

Dabei wird `isdttool` nicht aufgerufen. Demo- und Live-Verlauf liegen in
getrennten Datenbanken.

## Tests

```bash
cd ~/Downloads/isdt-nxhost-monitor
~/isdt-env/bin/python -m unittest discover -s tests -v
```

Die Tests prüfen die Offsets gegen sechs bisherige Frames, die Extraktion der
`Reading`-Zeile, Fehlerfälle, lokale Serverbindung und dass der Subprocess nur
diese feste, lesende Befehlsform benutzt:

```text
isdttool -d --output json metrics --channel N
```

Es gibt keine Lade-, Schreib-, Raw-Command-, Bootloader- oder Firmwarebefehle.

## Konfiguration

`config.json` enthält standardmäßig acht Slots als isdttool-Kanäle `0` bis `7`:

```json
{
  "channels": [0, 1, 2, 3, 4, 5, 6, 7],
  "poll_interval_seconds": 5,
  "command_timeout_seconds": 10,
  "max_history_per_slot": 5000,
  "isdttool": "~/isdt-env/bin/isdttool"
}
```

- Slot 1 entspricht Kanal 0, Slot 8 entspricht Kanal 7.
- `channels` kann auf andere oder weniger Kanäle geändert werden.
- Das Polling bleibt seriell: nie mehr als ein `isdttool`-Prozess gleichzeitig.
- `poll_interval_seconds` ist der Zielabstand zwischen vollständigen Zyklen. Ist
  ein Zyklus langsamer, beginnt der nächste direkt danach; es gibt keine
  parallelen Abfragen.
- Pro Slot bleiben höchstens `max_history_per_slot` Einträge erhalten.

Eine andere Konfiguration lässt sich so angeben:

```bash
~/isdt-env/bin/python main.py --config /voller/pfad/config.json
```

## Experimentelles Frame-Layout

Offsets sind nullbasiert und werden Little Endian gelesen:

| Offset | Breite | Vorläufige Deutung | Status |
|---:|---:|---|---|
| 13 | 2 | Spannung in mV | experimentell |
| 15 | 2 | Strom in mA | experimentell, nicht verifiziert |
| 17 | 2 | Widerstand in mΩ | experimentell, nicht verifiziert |
| 19 | 2 | Temperatur / 10 in °C | experimentell, nicht verifiziert |
| 21 | 2 | Unbekannt A (`uint16`) | unbekannt |
| 23 | 4 | Unbekannt B (`uint32`) | unbekannt |
| 27 | 4 | Unbekannt C (`uint32`) | unbekannt |

Beispiel Kanal 4: Aus dem Frame werden `1540`, `209`, `190`, `32,9`, `65`,
`25` und `446`. Beispiel Kanal 5 (spätere Abfrage): `1430`, `222`, `252`,
`32,6`, `70`, `28` und `462`. Diese Übereinstimmung bestätigt die angegebenen
Byte-Offsets für die Beispiele, nicht deren physikalische Bedeutung.

## Daten und CSV

- Live-Verlauf: `data/monitor.sqlite3`
- Demo-Verlauf: `data/demo.sqlite3`
- CSV: Schaltfläche **CSV herunterladen** im Dashboard
- Rohframe, vollständige `isdttool`-Ausgabe und Fehler werden pro Abfrage
  gespeichert und in der Diagnoseansicht sichtbar gemacht.

Für einen neuen Verlauf den Monitor beenden und die gewünschte SQLite-Datei im
Ordner `data` verschieben oder löschen. Das Dashboard legt sie beim nächsten
Start neu an.
