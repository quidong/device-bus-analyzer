"""MACS-Frames parsen und prüfen (für Mitschnitte aus macs-sniffer.yaml).

Frameaufbau (agocsdaniel/esphome_electrolux_macs, electrolux_macs.cpp):
  Nachricht: <0xC9> <Ziel> <Quelle> <Länge> <Daten …> <Prüfsumme>
  ACK:       <0x98> <Prüfsumme der empfangenen Nachricht> <Prüfsumme>
  Prüfsumme: XOR über alle vorherigen Bytes des Frames.

Hinweis: Die FINDINGS-Dateien im Repo schreiben den Marker als 0x9C, der Code
verwendet 0xC9 – der Parser akzeptiert beide.

Aufruf:  python3 macs_frames.py "C9 2A 21 02 5F 03 B6"
         python3 macs_frames.py < esphome.log   (Zeilen mit Hexbytes)
"""
import re
import sys

MSG_MARKERS = (0xC9, 0x9C)
ACK_MARKER = 0x98

DEVICES = {0x00: "Broadcast", 0x21: "WM-Steuerung", 0x22: "Trockner-Steuerung",
           0x25: "Inverter", 0x2A: "Bedienteil",
           0x30: "Kompressor-Board"}   # Trockner: meldet sich als "M1IB1606"
TYPES = {0x10: "Wakeup", 0x11: "Identifikation", 0x12: "Inverter-Status",
         0x50: "Programmwahl", 0x51: "Zustandswechsel", 0x52: "Gerätezustand",
         0x14: "Abfrage 0x14", 0x53: "Ein/Aus", 0x55: "Programm", 0x56: "Zeit",
         0x57: "Alarm", 0x5F: "Heartbeat"}


def checksum(data):
    c = 0
    for b in data:
        c ^= b
    return c


def build_frame(target, source, payload, marker=0xC9):
    body = [marker, target, source, len(payload), *payload]
    return bytes(body + [checksum(body)])


def parse_stream(data):
    """Zerlegt einen Bytestrom in Frames. Gibt Liste von dicts zurück."""
    frames, i = [], 0
    while i < len(data):
        b = data[i]
        if b in MSG_MARKERS and i + 4 <= len(data):
            n = data[i + 3]
            end = i + 5 + n
            if end <= len(data):
                raw = data[i:end]
                frames.append({
                    "kind": "msg", "target": raw[1], "source": raw[2],
                    "payload": bytes(raw[4:4 + n]),
                    "ok": checksum(raw[:-1]) == raw[-1], "raw": bytes(raw)})
                i = end
                continue
        if b == ACK_MARKER and i + 3 <= len(data):
            raw = data[i:i + 3]
            frames.append({"kind": "ack", "ok": checksum(raw[:-1]) == raw[-1],
                           "raw": bytes(raw)})
            i += 3
            continue
        i += 1
    return frames


def describe(f):
    if f["kind"] == "ack":
        return f"ACK {'ok' if f['ok'] else 'PRÜFSUMME FALSCH'}  {f['raw'].hex(' ')}"
    p = f["payload"]
    t = TYPES.get(p[0], f"0x{p[0]:02X}") if p else "-"
    return (f"{DEVICES.get(f['source'], hex(f['source']))} -> "
            f"{DEVICES.get(f['target'], hex(f['target']))}: {t:16s} "
            f"{p.hex(' ')}  {'ok' if f['ok'] else 'PRÜFSUMME FALSCH'}")


def hexbytes(text):
    """Hexbytes aus Text holen. ESPHome-Logzeilen ("<<< C9 2A …") werden
    erkannt; Zeitstempel und Präfixe davor werden ignoriert."""
    out = []
    for line in text.splitlines():
        if "<<<" in line:
            line = line.split("<<<", 1)[1]
        elif "[" in line:      # andere Logzeilen überspringen
            continue
        out += [int(h, 16) for h in re.findall(r"\b[0-9A-Fa-f]{2}\b", line)]
    return bytes(out)


if __name__ == "__main__":
    src = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    for fr in parse_stream(hexbytes(src)):
        print(describe(fr))
