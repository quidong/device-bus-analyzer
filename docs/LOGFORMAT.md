# Logformat 1 (D-Bus-Rohdaten über das ESPHome-Log)

Die Firmware schreibt Rohdaten und Zähler als Logzeilen mit dem Tag `dbus_raw`. Ein Sammler liest sie über die
ESPHome-API, speichert sie unverändert und dekodiert erst danach. Dasselbe Format gilt für jedes Gerät
(BSH-D-Bus, MACS-Bus des Electrolux/AEG-Trockners, weitere Busse).

## Zeilen

```
RAW1 seq=<n> t_us=<µs> dt_us=<µs> n=<Bytes> hex=<Rohbytes>
HB1  seq=<n> t_us=<µs> epoch=<s> bytes=<n> bursts=<n> ok=<n> crc=<n> noack=<n> rest=<n>
```

| Feld | Bedeutung |
|---|---|
| `seq` | laufende Nummer des Bursts seit Boot (lückenlos); im Heartbeat der letzte vergebene Wert |
| `t_us` | 64-Bit-Mikrosekunden seit Boot, überlaufsicher (32-Bit-Zähler wird alle 60 s mindestens einmal ausgelesen) |
| `dt_us` | Abstand zum vorigen Burst in µs |
| `n`, `hex` | Anzahl und Inhalt der Rohbytes eines Bursts, kleingeschrieben, ohne Trenner |
| `epoch` | Unix-Sekunden aus der Zeitquelle (Home Assistant), `0` wenn noch nicht synchronisiert |
| `bytes`, `bursts` | Summen seit Boot; `ok`, `crc`, `noack`, `rest` die Zähler der Firmware-Zerlegung |

Ein **Burst** sind alle Bytes bis zur ersten Ruhezeit auf dem Bus (BSH: 15 ms bei 9600 Baud). `t_us` ist der Zeitpunkt, an dem
diese Ruhe erkannt wurde, das Burstende liegt also etwa um die Ruhezeit früher. Ein Burst kann mehrere Telegramme enthalten.
Die Zerlegung in Telegramme macht der Sammler aus den Rohbytes. Die Zeilen `FRAME …` der Firmware sind nur eine Hilfe fürs Debuggen.

### MACS (Trockner)
Beim MACS-Bus sind die Pausen innerhalb eines Frames nicht verlässlich kürzer als die zwischen zwei Frames. Die Firmware
(`firmware/macs_recorder.h`) bildet Bursts deshalb frame-genau: ein Burst ist ein Frame mit seinem ACK, Bytes ohne Frame
bilden einen eigenen Burst. `t_us` ist der Zeitpunkt, an dem der Burst vollständig war (bis ca. 40 ms nach Busende, wenn
kein ACK kam). Das Format der Zeilen ist unverändert.

## Verlustprüfung
* `seq` springt in `RAW1`: es fehlen Bursts im Sammler (Verbindung unterbrochen oder Logzeilen verworfen).
* `HB1.seq` ≠ zuletzt gesehenes `RAW1.seq`: Bursts gingen auf dem Weg verloren.
* `t_us` fällt zurück: das Board wurde neu gestartet, neuer Abschnitt.
* Absolute Zeit = `epoch` des Heartbeats + (`t_us` − `t_us` des Heartbeats) / 10⁶.

Werkzeug: `dba gaps <log>`.

## Datenschutz
Vor dem Veröffentlichen von Logs: `dba sanitize raw.txt > clean.txt` (entfernt WLAN-Name, MAC, IP, Hostnamen, Schlüssel).
