"""
MACS-ESP32-C6 – universeller Adapter für den Electrolux/AEG/Zanussi MACS-Bus.

Schaltung als Code (SKiDL). Dieses Skript ist die "Quelle der Wahrheit":
daraus werden Netzliste, KiCad-Schaltplan und Leiterplatte erzeugt.

MACS-Bus (laut github.com/agocsdaniel/esphome_electrolux_macs):
  Stecker RAST 2.5, 4-polig: 1 = +12 V, 2 = +5 V, 3 = DATA, 4 = GND
  DATA: eine bidirektionale Leitung, 5-V-Pegel, invertiert (Ruhe = 0 V),
        9600 Baud, 8E1 (even parity)

Funktionsblöcke (v1.1, Aufbau angelehnt an Bouni/BSH-Board)
  * RAST-2.5-Direktsteckkante 4-polig (Stecker Lumberg 3517 04 K01 oder
    Würth WR-RAST 667101210104)
  * Schutz am Stecker: TVS SMF15A auf +12 V, Z-Dioden 5,6 V auf DATA und +5 V
  * Versorgung aus +12 V (Standard) oder +5 V (Lötbrücke JP2), plus USB-C
    – jede Quelle über Schottky-Diode entkoppelt
  * AP63203 Step-Down (3,8–32 V) auf feste 3,3 V
  * ESP32-C6-WROOM-1-N8 (Antenne ragt über die Platinenkante; WROOM statt
    MINI, damit JLCPCB in der günstigen Economic-Variante bestückt)
  * RX: Spannungsteiler 4k7/10k (5 V -> 3,4 V) + 1 nF Filter, UART "inverted"
  * TX: NPN + P-MOSFET High-Side-Treiber auf +5 V, 100 Ohm Serienwiderstand,
        dauerhaft verbunden; Basis-Pulldown hält ihn beim Booten aus
  * 12-V-Erkennung per ADC (GPIO0)
  * LEDs: Power (rot), Status (grün, GPIO8), Bus-Aktivität (blau, GPIO21)
"""
import os
import sys

os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

import builtins  # noqa: E402
from skidl import (  # noqa: E402
    Net, Part, SubCircuit, set_default_tool, generate_netlist, ERC,
)

set_default_tool("kicad7")

# --------------------------------------------------------------------------
# Bauteil-Stammdaten (JLCPCB/LCSC-Nummern; 0402-Passive = JLC-Basic-Teile,
# MINI-1, AP63203, Spule, Taster, Z-Dioden wie im BSH-Board von Bouni)
# --------------------------------------------------------------------------
LCSC = {
    "ESP32-C6-WROOM-1-N8": "C5366877",
    "AP63203WU": "C780769",
    "3.3uH": "C5832373",
    "TYPE-C-31-M-12": "C165948",
    "USBLC6-2SC6": "C7519",
    "MMBT3904": "C20526",
    "AO3401A": "C15127",
    "B5819W": "C8598",
    "SMF15A": "C353311",
    "BZX584C5V6": "C19077464",
    "LED_red": "C2286",
    "LED_green": "C12624",
    "LED_blue": "C965807",       # XL-1608UBC-04 (C72041 nicht lieferbar)
    "TS-3025-B-C-B": "C2689695",
    "10k": "C25744",
    "4.7k": "C25900",
    "5.1k": "C25905",
    "33k": "C25779",
    "100": "C25076",
    "1k": "C11702",
    "100nF": "C307331",
    "1nF": "C1523",
    "1uF": "C52923",
    "10uF": "C96446",
    "22uF": "C45783",
}

FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_C = "Capacitor_SMD:C_0402_1005Metric"
FP_C_10U = "Capacitor_SMD:C_0603_1608Metric"
FP_C_BULK = "Capacitor_SMD:C_0805_2012Metric"


def _tag(part, lcsc_key, mpn=None, dnp=False):
    part.fields["LCSC"] = LCSC.get(lcsc_key, "") if lcsc_key else ""
    if mpn:
        part.fields["MPN"] = mpn
    if dnp:
        part.fields["DNP"] = "1"
    return part


def R(value, ref=None):
    p = Part("Device", "R", value=value, footprint=FP_R)
    if ref:
        p.ref = ref
    return _tag(p, value)


def C(value, ref=None):
    fp = {"22uF": FP_C_BULK, "10uF": FP_C_10U}.get(value, FP_C)
    p = Part("Device", "C", value=value, footprint=fp)
    if ref:
        p.ref = ref
    return _tag(p, value)


def D(kind, value, lcsc_key, ref, fp):
    p = Part("Device", kind, value=value, footprint=fp)
    p.ref = ref
    return _tag(p, lcsc_key, value)


# ESP32-C6-WROOM-1: Symbol in lib/macs.kicad_sym (tools/make_esp_symbol.py),
# Footprint aus der Espressif-KiCad-Bibliothek (lib/macs.pretty).
HERE = os.path.dirname(os.path.abspath(__file__))
ESP_LIB = os.path.join(HERE, "lib", "macs.kicad_sym")

# Modul-Pinnummern der verwendeten GPIOs (ESP32-C6-WROOM-1)
ESP = {"3V3": 2, "EN": 3, "IO0": 8, "IO2": 27, "IO3": 26, "IO8": 10,
       "IO9": 15, "IO12": 13, "IO13": 14, "IO18": 16, "IO19": 17,
       "IO21": 19, "IO22": 20}
ESP_GND = [1, 28, 29]


def build():
    # ---------------------------------------------------------------- Netze
    gnd = Net("GND")
    v12_bus = Net("+12V_BUS")
    v5_bus = Net("+5V_BUS")
    macs = Net("MACS_DATA")
    vbus = Net("VBUS")
    v12_d = Net("V12_D")
    v5_d = Net("V5_D")
    vin = Net("VIN")
    v33 = Net("+3V3")
    sw = Net("SW")
    bst = Net("BST")
    en = Net("ESP_EN")
    boot = Net("BOOT_IO9")
    led_k = Net("LED_K")
    io8 = Net("LED_IO8")
    act = Net("LED_ACT")
    act_a = Net("ACT_A")
    pwr_a = Net("PWR_A")
    cc1, cc2 = Net("CC1"), Net("CC2")
    dp, dn = Net("USB_DP"), Net("USB_DN")
    macs_rx = Net("MACS_RX")
    macs_tx = Net("MACS_TX")
    q1_b = Net("Q1_B")
    q2_g = Net("Q2_G")
    tx_drv = Net("TX_DRV")
    v12_sense = Net("V12_SENSE")
    io2, io3, io22 = Net("IO2"), Net("IO3"), Net("IO22")

    # ------------------------------- MACS-Anschluss: RAST-2.5-Steckkante
    # Kein Bauteil: Kontakte sind Kupferflächen an der Platinenkante, darauf
    # wird derselbe Schneidklemm-Stecker gesteckt wie am Gerät.
    with SubCircuit("MACS_Stecker"):
        j = Part("Connector_Generic", "Conn_01x04", value="MACS_RAST2.5",
                 footprint="macs:RAST25_Direkt_1x04_K34")
        j.ref = "J2"
        _tag(j, None, dnp=True)
        j[1] += v12_bus
        j[2] += v5_bus
        j[3] += macs
        j[4] += gnd

        # Schutz direkt am Stecker (Störspitzen aus dem Gerät, ESD beim Stecken)
        d5 = D("D_Zener", "SMF15A", "SMF15A", "D5", "Diode_SMD:D_SOD-123F")
        d5["K"] += v12_bus
        d5["A"] += gnd
        d6 = D("D_Zener", "BZX584C5V6", "BZX584C5V6", "D6", "Diode_SMD:D_SOD-523")
        d6["K"] += macs
        d6["A"] += gnd
        d7 = D("D_Zener", "BZX584C5V6", "BZX584C5V6", "D7", "Diode_SMD:D_SOD-523")
        d7["K"] += v5_bus
        d7["A"] += gnd

    # ---------------------------------------------------------- Versorgung
    with SubCircuit("Versorgung"):
        d1 = D("D_Schottky", "B5819W", "B5819W", "D1", "Diode_SMD:D_SOD-123")
        d1["A"] += v12_bus
        d1["K"] += v12_d
        d3 = D("D_Schottky", "B5819W", "B5819W", "D3", "Diode_SMD:D_SOD-123")
        d3["A"] += v5_bus
        d3["K"] += v5_d
        d2 = D("D_Schottky", "B5819W", "B5819W", "D2", "Diode_SMD:D_SOD-123")
        d2["A"] += vbus
        d2["K"] += vin

        jp2 = Part("Jumper", "SolderJumper_3_Bridged12", value="VSEL_12V_5V",
                   footprint="Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm")
        jp2.ref = "JP2"
        _tag(jp2, None)
        jp2[1] += v12_d
        jp2[2] += vin
        jp2[3] += v5_d

        c1 = C("10uF", "C1")
        c2 = C("100nF", "C2")
        for c in (c1, c2):
            c[1] += vin
            c[2] += gnd

        # AP63203: 3,8–32 V Eingang, feste 3,3 V (kein Teiler), EN an VIN
        u2 = Part("Regulator_Switching", "AP63203WU", value="AP63203WU",
                  footprint="Package_TO_SOT_SMD:TSOT-23-6")
        u2.ref = "U2"
        _tag(u2, "AP63203WU", "AP63203WU-7")
        u2["IN"] += vin
        u2["EN"] += vin
        u2["GND"] += gnd
        u2["SW"] += sw
        u2["BST"] += bst
        u2["FB"] += v33
        c4 = C("100nF", "C4")
        c4[1] += bst
        c4[2] += sw
        l1 = Part("Device", "L", value="3.3uH", footprint="Inductor_SMD:L_1008_2520Metric")
        l1.ref = "L1"
        _tag(l1, "3.3uH", "3.3uH 1008")
        l1[1] += sw
        l1[2] += v33
        for ref in ("C3", "C5"):
            c = C("22uF", ref)
            c[1] += v33
            c[2] += gnd

        # 12-V-Erkennung: 33k/10k -> max. 3,26 V bei 14 V, 100 nF glättet
        r4 = R("33k", "R4")
        r4[1] += v12_bus
        r4[2] += v12_sense
        r5 = R("10k", "R5")
        r5[1] += v12_sense
        r5[2] += gnd
        c11 = C("100nF", "C11")
        c11[1] += v12_sense
        c11[2] += gnd

        # Power-LED
        r17 = R("1k", "R17")
        r17[1] += v33
        r17[2] += pwr_a
        d8 = D("LED", "red", "LED_red", "D8", "LED_SMD:LED_0603_1608Metric")
        d8["A"] += pwr_a
        d8["K"] += gnd

    # ------------------------------------------------------------ ESP32-C6
    with SubCircuit("ESP32_C6"):
        u1 = Part(ESP_LIB, "ESP32-C6-WROOM-1", value="ESP32-C6-WROOM-1-N8",
                  footprint="macs:ESP32-C6-WROOM-1")
        u1.ref = "U1"
        _tag(u1, "ESP32-C6-WROOM-1-N8", "ESP32-C6-WROOM-1-N8")
        for p in ESP_GND:
            u1[p] += gnd
        u1[ESP["3V3"]] += v33
        u1[ESP["EN"]] += en
        u1[ESP["IO0"]] += v12_sense
        u1[ESP["IO2"]] += io2
        u1[ESP["IO3"]] += io3
        u1[ESP["IO22"]] += io22
        u1[ESP["IO8"]] += io8
        u1[ESP["IO9"]] += boot
        u1[ESP["IO12"]] += dn
        u1[ESP["IO13"]] += dp
        u1[ESP["IO18"]] += macs_rx
        u1[ESP["IO19"]] += macs_tx
        u1[ESP["IO21"]] += act

        c7 = C("100nF", "C7")
        c8 = C("10uF", "C8")
        for c in (c7, c8):
            c[1] += v33
            c[2] += gnd

        # EN: 10k / 1uF (Espressif-Empfehlung) + Reset-Taster
        r6 = R("10k", "R6")
        r6[1] += v33
        r6[2] += en
        c9 = C("1uF", "C9")
        c9[1] += en
        c9[2] += gnd

        # Taster nicht bestückt (DNP): Flashen geht über USB auch ohne BOOT,
        # im dichten Gehäuse kommt man nicht dran; Pads bleiben zum Nachlöten.
        for ref, net, label in (("SW1", boot, "BOOT"), ("SW2", en, "RESET")):
            s = Part("Switch", "SW_Push", value=label, footprint="macs:SW_TS-3025")
            s.ref = ref
            _tag(s, "TS-3025-B-C-B", "TS-3025-B-C-B", dnp=True)
            s[1] += net
            s[2] += gnd

        r7 = R("10k", "R7")
        r7[1] += v33
        r7[2] += boot

        # Status-LED aktiv-low an GPIO8 (hält Strapping-Pin beim Boot high)
        d4 = D("LED", "green", "LED_green", "D4", "LED_SMD:LED_0603_1608Metric")
        d4["A"] += v33
        d4["K"] += led_k
        r8 = R("1k", "R8")
        r8[1] += led_k
        r8[2] += io8

        # Bus-Aktivität (GPIO21, aktiv high; ESPHome blinkt bei jedem Frame)
        r18 = R("1k", "R18")
        r18[1] += act
        r18[2] += act_a
        d9 = D("LED", "blue", "LED_blue", "D9", "LED_SMD:LED_0603_1608Metric")
        d9["A"] += act_a
        d9["K"] += gnd

    # --------------------------------------------------------------- USB-C
    with SubCircuit("USB_C"):
        j1 = Part("Connector", "USB_C_Receptacle_USB2.0_16P", value="USB-C",
                  footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12")
        j1.ref = "J1"
        _tag(j1, "TYPE-C-31-M-12", "TYPE-C-31-M-12")
        for p in ("A1", "A12", "B1", "B12", "S1"):
            j1[p] += gnd
        for p in ("A4", "A9", "B4", "B9"):
            j1[p] += vbus
        j1["A5"] += cc1
        j1["B5"] += cc2
        j1["A6"] += dp
        j1["B6"] += dp
        j1["A7"] += dn
        j1["B7"] += dn

        r9 = R("5.1k", "R9")
        r9[1] += cc1
        r9[2] += gnd
        r10 = R("5.1k", "R10")
        r10[1] += cc2
        r10[2] += gnd

        u3 = Part("Power_Protection", "USBLC6-2SC6", value="USBLC6-2SC6",
                  footprint="Package_TO_SOT_SMD:SOT-23-6")
        u3.ref = "U3"
        _tag(u3, "USBLC6-2SC6", "USBLC6-2SC6")
        u3[1] += dp
        u3[6] += dp
        u3[3] += dn
        u3[4] += dn
        u3[2] += gnd
        u3[5] += vbus

    # ------------------------------------------------------- MACS RX-Pfad
    with SubCircuit("MACS_RX"):
        r11 = R("4.7k", "R11")
        r11[1] += macs
        r11[2] += macs_rx
        r12 = R("10k", "R12")
        r12[1] += macs_rx
        r12[2] += gnd
        # 1 nF: mit 3,2 kOhm Quellwiderstand tau = 3 us << 104 us Bitzeit
        c10 = C("1nF", "C10")
        c10[1] += macs_rx
        c10[2] += gnd

    # ------------------------------------------------------- MACS TX-Pfad
    with SubCircuit("MACS_TX"):
        r13 = R("4.7k", "R13")
        r13[1] += macs_tx
        r13[2] += q1_b
        r14 = R("10k", "R14")
        r14[1] += q1_b
        r14[2] += gnd

        q1 = Part("Transistor_BJT", "MMBT3904", value="MMBT3904",
                  footprint="Package_TO_SOT_SMD:SOT-23")
        q1.ref = "Q1"
        _tag(q1, "MMBT3904", "MMBT3904")
        q1["B"] += q1_b
        q1["E"] += gnd
        q1["C"] += q2_g

        r15 = R("10k", "R15")
        r15[1] += v5_bus
        r15[2] += q2_g

        q2 = Part("Transistor_FET", "AO3401A", value="AO3401A",
                  footprint="Package_TO_SOT_SMD:SOT-23")
        q2.ref = "Q2"
        _tag(q2, "AO3401A", "AO3401A")
        q2["G"] += q2_g
        q2["S"] += v5_bus
        q2["D"] += tx_drv

        r16 = R("100", "R16")
        r16[1] += tx_drv
        r16[2] += macs

    # ------------------------------------------- Testpunkte / Erweiterung
    with SubCircuit("Testpunkte"):
        for ref, net, val in (("TP1", macs, "DATA"), ("TP2", gnd, "GND"),
                              ("TP3", v33, "3V3"), ("TP4", v5_bus, "5V"),
                              ("TP5", io2, "IO2"), ("TP6", io3, "IO3"),
                              ("TP7", io22, "IO22")):
            tp = Part("Connector", "TestPoint", value=val,
                      footprint="TestPoint:TestPoint_Pad_D1.0mm")
            tp.ref = ref
            _tag(tp, None)
            tp[1] += net

    # stabile Tags (gleichbleibende Zeitstempel/UUIDs bei jedem Lauf)
    for part in builtins.default_circuit.parts:
        part.tag = part.ref
    return builtins.default_circuit


def make_schematic(out_dir):
    """KiCad-Schaltplan (hierarchisch, Netzlabel-Stil) erzeugen und in das
    KiCad-7-Format bringen (öffnet auch in KiCad 8/9/10)."""
    import shutil
    import tempfile
    sys.path.insert(0, os.path.join(HERE, "tools"))
    from sch_to_kicad7 import main as to_k7
    circ = builtins.default_circuit
    tmp = tempfile.mkdtemp()
    circ.generate_schematic(filepath=tmp, top_name="macs_esp32c6",
                            title="MACS-ESP32-C6 Adapter", mode="labels",
                            flatness=0)
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".kicad_sch"):
            os.remove(os.path.join(out_dir, f))
    to_k7(tmp, out_dir)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import sys
    build()
    ERC()
    out = sys.argv[1] if len(sys.argv) > 1 else "macs_esp32c6.net"
    generate_netlist(file_=out)
    print("Netzliste geschrieben:", out)
    if "--schematic" in sys.argv:
        sch_dir = os.path.dirname(os.path.abspath(out))   # neben .kicad_pro/.kicad_pcb
        make_schematic(sch_dir)
        print("Schaltplan geschrieben:", sch_dir)
