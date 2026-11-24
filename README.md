# ISDT NXHOST Battery Monitor für macOS

Lokales Python-Web-Dashboard für experimentell dekodierte NXHOST-Messframes. Es
fragt die konfigurierten Kanäle **nacheinander** ab, speichert den Verlauf in
SQLite, zeigt Rohdaten und Fehler an und exportiert alle gespeicherten Messungen
als CSV.

> **Wichtiger Status:** Das Protokoll bleibt experimentell und reverse
> engineered. Spannung, Temperatur, Widerstand und Kapazität wurden am
> 15. November 2026 mit einer rein lesenden Live-Abfrage gegen die gleichzeitig
> angezeigten Slotwerte abgeglichen. Dies ist kein umfassender Hardwaretest.
> Momentanstrom, Prozent/Status, Ladezeit und weitere Rohwerte bleiben
> vorläufig.

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

Mit **Inaktive Slots ausblenden** lassen sich Karten ohne dekodierte Messwerte
verbergen. Die Einstellung bleibt lokal im Browser gespeichert; Verlauf und
Rohdaten werden dadurch nicht gelöscht.

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

## Automatisch bei USB-Verbindung öffnen (macOS)

Die angeschlossene N-Series meldet sich auf diesem Mac als `ISDTNX` mit der
USB-ID `28E9:028A`. Der mitgelieferte lokale Wächter prüft ausschließlich diese
Kennung in der macOS-USB-Liste. Er sendet dabei keine Befehle an das Ladegerät.

Zum Aktivieren `install-autostart.command` doppelklicken. Danach läuft beim
Anmelden ein persönlicher macOS-LaunchAgent:

- Beim Anstecken von `ISDTNX` startet er den Monitor, falls dieser noch nicht
  läuft, und öffnet einmalig `http://127.0.0.1:8765/`.
- Beim Abziehen beendet er nur einen Monitor, den er selbst gestartet hat. Ein
  manuell gestarteter Monitor bleibt unangetastet.
- Andere USB-Geräte lösen nichts aus. Alles bleibt lokal auf diesem Mac.

Mit `uninstall-autostart.command` lässt sich die Automatik vollständig wieder
entfernen. Die Messdatenbank wird dabei nicht gelöscht.

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

Die Tests prüfen die Offsets gegen historische und live abgeglichene Frames,
einschließlich NXHOST-Byte-Stuffing, die Extraktion der `Reading`-Zeile,
Fehlerfälle, lokale Serverbindung und dass der Subprocess nur
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
  "slot_labels": {
    "4": "Eneloop",
    "5": "Eneloop",
    "6": "Eneloop",
    "7": "NiMH · Analyse"
  },
  "poll_interval_seconds": 5,
  "notifications_enabled": true,
  "command_timeout_seconds": 10,
  "max_history_per_slot": 5000,
  "isdttool": "~/isdt-env/bin/isdttool"
}
```

- Slot 1 entspricht Kanal 0, Slot 8 entspricht Kanal 7.
- `channels` kann auf andere oder weniger Kanäle geändert werden.
- `slot_labels` sind manuelle Bezeichnungen. `metrics` überträgt keinen Text
  wie „Eneloop“; der Monitor behauptet daher keine automatische Erkennung.
- Das Polling bleibt seriell: nie mehr als ein `isdttool`-Prozess gleichzeitig.
- `notifications_enabled` aktiviert eine lokale macOS-Mitteilung, wenn ein
  beobachteter Ladevorgang von aktiv auf vollständig geladen wechselt. Pro
  Vorgang erscheint genau eine Mitteilung; beim Programmstart bereits volle
  Akkus lösen keine nachträgliche Meldung aus.
- Die Live-Karten markieren den beobachteten aktiven Ladecode 3 zusammen mit
  positivem Strom als orangefarbenen, animierten Zustand `LÄDT`. Der bestätigte
  Fertigcode 4 mit 0 mA bleibt als ruhiger grüner Zustand `VOLL GELADEN` sichtbar.
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
| 9 | 1 | Akku eingesetzt | Kandidat: 1 bei belegten, 4 bei leeren Slots |
| 10 | 1 | Temperatur in °C | Display-Abgleich 25/25/26/26 °C |
| 12 | 1 | Status-/Prozent-Code | 99 bei zwei Slots mit Displaywert 99 %; 1 und 5 bei grünen, vollständig geladenen Slots; nicht als reiner Prozentwert interpretieren |
| 13 | 2 | Spannung in mV | Display-Abgleich an vier Slots |
| 15 | 2 | Momentanstrom in mA | 408/434 mA passen zu aktiven 0,4-A-Slots; sonst 0 |
| 17 | 2 | Widerstand in mΩ | Display-Abgleich 166/177/228/176 mΩ |
| 19 | 2 | unbekannter Rohwert (`uint16`) | frühere Temperaturannahme widerlegt |
| 21 | 2 | Unbekannt A (`uint16`) | unbekannt |
| 23 | 4 | Kapazität in mAh | 84 und 82 exakt; aktive Slots stiegen erwartbar weiter |
| 27 | 4 | verstrichene Zeit in Sekunden | plausibler Kandidat, nicht abschließend bestätigt |

Ein Live-Frame von Slot 7 enthielt eine gestuffte Nutzdatenfolge `AA AA 05`.
Nach protokollgerechtem Entstören zu `AA 05` ergeben sich exakt `1450 mV`,
`434 mA`, `228 mΩ` und `26 °C`. Der Parser berücksichtigt dieses Byte-Stuffing.

Beim Umstecken zweier Akkus meldeten die nun leeren Slots 5 und 8 weiterhin
eine Rest-/Leerlaufspannung von 773 beziehungsweise 793 mV. Gleichzeitig waren
Strom, Widerstand, Kapazität und Status null, und Byte 9 wechselte auf 4; bei
allen belegten Slots stand es auf 1. Die Oberfläche verwendet deshalb Byte 9
als experimentellen Belegungsindikator und nicht mehr „Spannung größer null“.

Die Displaybezeichnung „Eneloop“ ist im `metrics`-Frame nicht als Text enthalten.
Bei der gemeinsamen Umstellung von Slot 8 von Eneloop/Laden auf NiMH/Analyse
änderten sich die Rohcodes Byte 7/8 von `4/7` auf `11/9`; Byte 9/11 blieben
`1/23`. Weil Akkutyp und Vorgang gleichzeitig geändert wurden, lässt sich noch
nicht seriös zuordnen, welcher der beiden Codes für NiMH beziehungsweise Analyse
steht. Der Monitor zeigt diese vier Werte deshalb nur als Profil-/Moduscodes in
der Diagnose an. Die Namen in `slot_labels` sind ausdrücklich manuell.

Beim Neustart der Analyse fielen die Offset-23/27-Werte auf `1 mAh` und `27 s`.
Das stützt die Deutung als Kapazität und verstrichene Vorgangszeit zusätzlich.

Die Oberfläche zeigt Byte 12 während eines laufenden Vorgangs als
experimentellen Prozentwert. Der gemeinsam beobachtete Fertigzustand mit
Byte 7 = 4 und Strom = 0 wird zu 100 % normalisiert. Byte 12 lieferte dabei je
nach Slot beziehungsweise Vorgang die Rohcodes 1 oder 5 und ist daher im
Fertigzustand kein Prozentwert. Der ursprüngliche Rohcode bleibt weiterhin in
der Diagnoseansicht sichtbar.

## Daten und CSV

- Live-Verlauf: `data/monitor.sqlite3`
- Demo-Verlauf: `data/demo.sqlite3`
- CSV: Schaltfläche **CSV herunterladen** im Dashboard
- Rohframe, vollständige `isdttool`-Ausgabe und Fehler werden pro Abfrage
  gespeichert und in der Diagnoseansicht sichtbar gemacht.

Für einen neuen Verlauf den Monitor beenden und die gewünschte SQLite-Datei im
Ordner `data` verschieben oder löschen. Das Dashboard legt sie beim nächsten
Start neu an.
