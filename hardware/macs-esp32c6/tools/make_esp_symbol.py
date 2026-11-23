"""Erzeugt lib/macs.kicad_sym mit einem KiCad-7-Symbol für ESP32-C6-WROOM-1.

Pinbelegung nach Espressif-Datenblatt ESP32-C6-WROOM-1 (Tabelle „Pin
Definitions“), abgeglichen mit der offiziellen Espressif-KiCad-Bibliothek
(github.com/espressif/kicad-libraries, Symbol „ESP32-C6-WROOM-1“).
WROOM-1 statt MINI-1, weil JLCPCB das MINI-1 nur in der teuren
Standard-Bestückung verarbeitet. Masse-Pins 1, 28, 29 (EPAD) gestapelt.
"""
import sys

GND_PINS = [1, 28, 29]
PINS = {  # Nummer: (Name, Typ)
    2: ("3V3", "power_in"), 3: ("EN", "input"),
    8: ("IO0", "bidirectional"), 9: ("IO1", "bidirectional"),
    27: ("IO2", "bidirectional"), 26: ("IO3", "bidirectional"),
    4: ("IO4", "bidirectional"), 5: ("IO5", "bidirectional"),
    6: ("IO6", "bidirectional"), 7: ("IO7", "bidirectional"),
    10: ("IO8", "bidirectional"), 15: ("IO9", "bidirectional"),
    11: ("IO10", "bidirectional"), 12: ("IO11", "bidirectional"),
    13: ("IO12/USB_D-", "bidirectional"), 14: ("IO13/USB_D+", "bidirectional"),
    23: ("IO15", "bidirectional"),
    25: ("TXD0/IO16", "bidirectional"), 24: ("RXD0/IO17", "bidirectional"),
    16: ("IO18", "bidirectional"), 17: ("IO19", "bidirectional"),
    18: ("IO20", "bidirectional"), 19: ("IO21", "bidirectional"),
    20: ("IO22", "bidirectional"), 21: ("IO23", "bidirectional"),
}
NC_PINS = [22]

LEFT = [2, 3, 8, 9, 27, 26, 4, 5, 6, 7, 10, 15, 11]
RIGHT = [12, 13, 14, 23, 25, 24, 16, 17, 18, 19, 20, 21]

STEP = 2.54
X = 15.24
TOP = 15.24


def pin(num, name, typ, x, y, rot, hide=False):
    h = " hide" if hide else ""
    return (f'      (pin {typ} line (at {x:.2f} {y:.2f} {rot}) (length 2.54){h}\n'
            f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{num}" (effects (font (size 1.27 1.27))))\n'
            f'      )\n')


def main(path):
    bottom = TOP - STEP * (len(LEFT) - 1) - 2 * STEP
    n = "ESP32-C6-WROOM-1"
    out = ['(kicad_symbol_lib (version 20220914) (generator macs_board)\n',
           f'  (symbol "{n}" (in_bom yes) (on_board yes)\n',
           f'    (property "Reference" "U" (at -12.7 {TOP + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n',
           f'    (property "Value" "{n}" (at -12.7 {bottom - 6.35:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n',
           f'    (property "Footprint" "macs:{n}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n',
           '    (property "Datasheet" "https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n',
           f'    (symbol "{n}_0_1"\n',
           f'      (rectangle (start -12.7 {TOP + 2.54:.2f}) (end 12.7 {bottom:.2f}) '
           '(stroke (width 0.254) (type default)) (fill (type background)))\n',
           '    )\n',
           f'    (symbol "{n}_1_1"\n']
    for i, p in enumerate(LEFT):
        out.append(pin(p, *PINS[p], -X, TOP - i * STEP, 0))
    for i, p in enumerate(RIGHT):
        out.append(pin(p, *PINS[p], X, TOP - i * STEP, 180))
    for k, p in enumerate(GND_PINS):           # gestapelt, nur der erste sichtbar
        out.append(pin(p, "GND", "power_in" if k == 0 else "passive",
                       0, bottom - 2.54, 90, hide=k > 0))
    for k, p in enumerate(NC_PINS):
        out.append(pin(p, "NC", "no_connect", -10.16 + k * 2.54, TOP + 5.08, 270, hide=True))
    out += ['    )\n', '  )\n', ')\n']
    with open(path, "w") as f:
        f.write("".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lib/macs.kicad_sym")
