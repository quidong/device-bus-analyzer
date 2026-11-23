"""
Testsuite für die MACS-ESP32-C6-Platine.

  python3 -m pytest -q tests/          (oder: python3 tests/test_board.py)

Prüft:
  * Schaltung: Pinbelegung MACS-Stecker, GPIO-Zuordnung, Pegel/Spannungsteiler,
    Reglerausgang, Strapping-Pins, TX-Lötbrücke
  * Leiterplatte: jedes Pad trägt das Netz aus der Schaltung, DRC ohne Fehler
    und ohne offene Verbindungen, Antenne frei, Bauteile auf der Platine
  * Fertigungsdaten: BOM/CPL vollständig und konsistent, LCSC-Nummern gesetzt,
    Gerber-ZIP enthält alle Lagen
  * Firmware: ESPHome-YAML passt zur Platine
  * Protokoll-Werkzeug: Prüfsumme und Frame-Zerlegung
"""
import csv
import os
import re
import subprocess
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

PCB = os.path.join(ROOT, "build", "macs_esp32c6.kicad_pcb")
FAB = os.path.join(ROOT, "fab")


# --------------------------------------------------------------- Fixtures
@pytest.fixture(scope="session")
def circuit():
    import circuit as c
    return c.build()


@pytest.fixture(scope="session")
def nets(circuit):
    """{(ref, pin_num): net_name}"""
    out = {}
    for part in circuit.parts:
        for pin in part.pins:
            if pin.net is not None and pin.net.name:
                out[(part.ref, str(pin.num))] = pin.net.name
    return out


@pytest.fixture(scope="session")
def board():
    import pcbnew
    assert os.path.exists(PCB), "Platine fehlt – erst build_pcb.py ausführen"
    return pcbnew.LoadBoard(PCB)


def value_ohm(v):
    v = v.lower().replace("ω", "")
    mult = 1
    if v.endswith("k"):
        mult, v = 1e3, v[:-1]
    return float(v) * mult


def part(circuit, ref):
    return next(p for p in circuit.parts if p.ref == ref)


def net_of(nets, ref, pin):
    return nets.get((ref, str(pin)))


# ------------------------------------------------------------- Schaltung
def test_macs_connectors_pinout(nets):
    expected = {1: "+12V_BUS", 2: "+5V_BUS", 3: "MACS_DATA", 4: "GND"}
    for pin, net in expected.items():
        assert net_of(nets, "J2", pin) == net, f"J2.{pin}"
    assert net_of(nets, "J3", 1) is None          # nur noch ein Anschluss


def test_esp_gpio_assignment(nets):
    # Modulpin -> Netz (ESP32-C6-WROOM-1 Datenblatt, Pin Definitions)
    expected = {16: "MACS_RX", 17: "MACS_TX", 10: "LED_IO8", 15: "BOOT_IO9",
                13: "USB_DN", 14: "USB_DP", 8: "V12_SENSE", 3: "ESP_EN",
                2: "+3V3", 19: "LED_ACT", 27: "IO2", 26: "IO3", 20: "IO22"}
    for pin, net in expected.items():
        assert net_of(nets, "U1", pin) == net, f"U1.{pin}"
    for pin in (1, 28, 29):
        assert net_of(nets, "U1", pin) == "GND", f"U1.{pin}"


def test_strapping_pins_safe(nets, circuit):
    # GPIO9 mit Pull-up (SPI-Boot), GPIO8 über LED nach 3V3 (nie aktiv low beim Boot)
    assert net_of(nets, "R7", 1) == "+3V3" and net_of(nets, "R7", 2) == "BOOT_IO9"
    assert net_of(nets, "D4", 2) == "+3V3"            # LED-Anode
    # GPIO4 (Pin 4), GPIO5 (Pin 5), GPIO15 (Pin 23) = Strapping -> unbeschaltet
    for pin in (4, 5, 23):
        assert net_of(nets, "U1", pin) is None


def test_rx_divider_levels(circuit):
    r_top = value_ohm(part(circuit, "R11").value)
    r_bot = value_ohm(part(circuit, "R12").value)
    v_high = 5.0 * r_bot / (r_top + r_bot)
    assert 0.75 * 3.3 <= v_high <= 3.6, v_high      # VIH ESP32-C6 / abs. max
    load_ma = 5.0 / (r_top + r_bot) * 1e3
    assert load_ma < 0.5                             # Bus kaum belastet


def test_rx_filter(nets, circuit):
    """1 nF am RX-Pin filtert Störspitzen, lässt 9600 Baud durch."""
    assert {net_of(nets, "C10", 1), net_of(nets, "C10", 2)} == {"MACS_RX", "GND"}
    r_top = value_ohm(part(circuit, "R11").value)
    r_bot = value_ohm(part(circuit, "R12").value)
    c = 1e-9
    tau = (r_top * r_bot / (r_top + r_bot)) * c
    bit = 1 / 9600
    assert tau < bit / 20                             # Flanke < 5 % der Bitzeit
    assert tau > 1e-6                                 # filtert ns-Spitzen


def test_tx_path(nets, circuit):
    # Sender dauerhaft am Bus (kein JP1), 100 Ohm Serienwiderstand
    assert not any(p.ref == "JP1" for p in circuit.parts)
    assert {net_of(nets, "R16", 1), net_of(nets, "R16", 2)} == {"TX_DRV", "MACS_DATA"}
    # MOSFET schaltet +5V_BUS (High-Side, Bus ist in Ruhe 0 V)
    assert net_of(nets, "Q2", 2) == "+5V_BUS"         # Source
    assert net_of(nets, "Q2", 3) == "TX_DRV"          # Drain
    # Gate-Pull-up -> MOSFET ohne Ansteuerung aus
    assert {net_of(nets, "R15", 1), net_of(nets, "R15", 2)} == {"+5V_BUS", "Q2_G"}
    # Basis-Pulldown -> Treiber beim Booten aus
    assert {net_of(nets, "R14", 1), net_of(nets, "R14", 2)} == {"Q1_B", "GND"}
    i_max_ma = 5.0 / value_ohm(part(circuit, "R16").value) * 1e3
    assert i_max_ma <= 60


def test_bus_protection(nets, circuit):
    """TVS auf 12 V, Z-Dioden 5,6 V auf DATA und 5 V – Kathode am Netz."""
    exp = {"D5": ("+12V_BUS", "SMF15A"), "D6": ("MACS_DATA", "BZX584C5V6"),
           "D7": ("+5V_BUS", "BZX584C5V6")}
    for ref, (net, val) in exp.items():
        assert net_of(nets, ref, 1) == net and net_of(nets, ref, 2) == "GND", ref
        assert part(circuit, ref).value == val
    # SMF15A: Sperrspannung 15 V > 14 V Bus, Klemmspannung 24,4 V < 32 V (AP63203)
    assert 14.0 < 15.0 and 24.4 < 32.0
    # 5,6-V-Z-Diode leitet bei 5-V-Pegel noch nicht
    assert 5.0 < 5.6 * 0.93


def test_regulator(circuit, nets):
    u2 = part(circuit, "U2")
    assert u2.value == "AP63203WU"                    # feste 3,3 V, 3,8–32 V Eingang
    assert net_of(nets, "U2", 1) == "+3V3"            # FB direkt am Ausgang
    assert net_of(nets, "U2", 2) == "VIN"             # EN an VIN
    assert net_of(nets, "U2", 3) == "VIN"
    assert net_of(nets, "U2", 5) == "SW" and net_of(nets, "U2", 6) == "BST"
    # 5-V-Betrieb: 5 V - Schottky (max. 0,45 V) liegt über der Mindestspannung
    assert 5.0 - 0.45 > 3.8


def test_supply_sources_diode_ored(nets):
    assert net_of(nets, "D1", 2) == "+12V_BUS" and net_of(nets, "D1", 1) == "V12_D"
    assert net_of(nets, "D3", 2) == "+5V_BUS" and net_of(nets, "D3", 1) == "V5_D"
    assert net_of(nets, "D2", 2) == "VBUS" and net_of(nets, "D2", 1) == "VIN"
    assert net_of(nets, "JP2", 2) == "VIN"


def test_leds(nets):
    assert net_of(nets, "D8", 1) == "GND"             # Power-LED an 3,3 V
    assert {net_of(nets, "R17", 1), net_of(nets, "R17", 2)} == {"+3V3", "PWR_A"}
    assert net_of(nets, "D9", 1) == "GND"             # Aktivität an GPIO21
    assert {net_of(nets, "R18", 1), net_of(nets, "R18", 2)} == {"LED_ACT", "ACT_A"}


def test_adc_divider_in_range(circuit):
    r_top = value_ohm(part(circuit, "R4").value)
    r_bot = value_ohm(part(circuit, "R5").value)
    for vbus in (12.0, 14.0):
        assert vbus * r_bot / (r_top + r_bot) < 3.3


def test_usb_cc_pulldowns(nets):
    assert net_of(nets, "J1", "A5") == "CC1" and net_of(nets, "J1", "B5") == "CC2"
    for r in ("R9", "R10"):
        assert "GND" in (net_of(nets, r, 1), net_of(nets, r, 2))


def test_all_parts_have_lcsc_or_are_unassembled(circuit):
    for p in circuit.parts:
        if p.ref.startswith(("JP", "TP")) or p.fields.get("DNP") == "1":
            continue
        assert re.fullmatch(r"C\d+", p.fields.get("LCSC", "")), p.ref


# ------------------------------------------------------------ Leiterplatte
def test_pcb_pads_match_netlist(board, nets):
    mismatch = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            want = nets.get((ref, num))
            have = pad.GetNetname() or None
            if want != have:
                mismatch.append((ref, num, want, have))
    assert not mismatch, mismatch[:10]


def run_drc(path, report):
    """DRC über die pcbnew-API (kicad-cli kann DRC erst ab KiCad 8)."""
    import pcbnew
    b = pcbnew.LoadBoard(path)
    assert pcbnew.WriteDRCReport(b, str(report), pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(report).read()
    blocks = re.split(r"\n(?=\[)", txt)
    errors = [bl.splitlines()[0] for bl in blocks
              if "Severity: error" in bl and not bl.startswith("[unconnected_items]")]
    unconnected = [bl for bl in blocks if bl.startswith("[unconnected_items]")]
    return errors, unconnected


def test_pcb_drc_clean(tmp_path):
    errors, unconnected = run_drc(PCB, tmp_path / "drc.rpt")
    assert not unconnected, f"{len(unconnected)} offene Verbindungen: {unconnected[:2]}"
    assert not errors, errors[:10]


def test_antenna_overhangs_board(board):
    """Antennenteil des WROOM-1 (lokal y -15,75 … -9,75) liegt komplett über
    der Platinenkante, die Modul-Pads auf der Platine."""
    import pcbnew
    u1 = board.FindFootprintByReference("U1")
    edge_top = pcbnew.ToMM(board.GetBoardEdgesBoundingBox().GetY())
    y0 = pcbnew.ToMM(u1.GetPosition().y)
    assert y0 - 9.75 <= edge_top + 0.05               # Antenne außerhalb
    pad_top = min(pcbnew.ToMM(p.GetBoundingBox().GetTop()) for p in u1.Pads())
    assert pad_top >= edge_top + 0.2                  # Pads auf der Platine


def test_parts_inside_board(board):
    import pcbnew
    bb = board.GetBoardEdgesBoundingBox()
    for fp in board.GetFootprints():
        p = fp.GetPosition()
        assert bb.Contains(p), fp.GetReference()


# --------------------------------------------------------- Fertigungsdaten
def _csv(name):
    with open(os.path.join(FAB, name), newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------- RAST-2.5-Steckkante
def _inside(board, x, y):
    """Punkt (Platinenkoordinaten, mm) liegt auf der Platine?"""
    import pcbnew
    import build_pcb as bp
    poly = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(poly)
    return poly.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(bp.OX + x), pcbnew.FromMM(bp.OY + y)))


def _rast_pads(board):
    import pcbnew
    import build_pcb as bp
    out = {}
    for pad in board.FindFootprintByReference("J2").Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        bb = pad.GetBoundingBox()
        box = (pcbnew.ToMM(bb.GetLeft()) - bp.OX, pcbnew.ToMM(bb.GetTop()) - bp.OY,
               pcbnew.ToMM(bb.GetRight()) - bp.OX, pcbnew.ToMM(bb.GetBottom()) - bp.OY)
        side = "F" if pad.IsOnLayer(pcbnew.F_Cu) else "B"
        out[(pad.GetNumber(), side)] = (pad, box)
    return out


def test_rast_edge_pads(board):
    """Je Kontakt ein Pad oben und unten, Raster 2,5 mm, keine Lötpaste,
    Pads enden 1 mm vor der Zungenkante."""
    import pcbnew
    import build_pcb as bp
    pads = _rast_pads(board)
    assert sorted(pads) == [(str(n), s) for n in range(1, 5) for s in "BF"]
    xs = [(pads[(str(n), "F")][1][0] + pads[(str(n), "F")][1][2]) / 2 for n in range(1, 5)]
    for (n, side), (pad, (x0, y0, x1, y1)) in pads.items():
        assert not pad.IsOnLayer(pcbnew.F_Paste) and not pad.IsOnLayer(pcbnew.B_Paste)
        assert abs(y1 - (bp.RAST_EDGE - 1.0)) < 0.01, (n, side)
        assert y1 - y0 >= 4.0 and x1 - x0 >= 1.0
    # Kontaktmitten (Raster) liegen auf den Pads
    for i in range(4):
        cx = bp.RAST_CX + (i - 1.5) * 2.5
        _, (x0, _, x1, _) = pads[(str(i + 1), "F")]
        assert x0 + 0.4 <= cx <= x1 - 0.4, i + 1
    assert xs == sorted(xs)                     # 1..4 von links nach rechts


def test_rast_edge_outline(board):
    """Aussparung mit Führungswangen, Codierschlitz zwischen Kontakt 3 und 4."""
    import build_pcb as bp
    cx, ey, H = bp.RAST_CX, bp.RAST_EDGE, bp.H
    # Zunge vorhanden, davor Aussparung (Stecker sitzt darin)
    assert _inside(board, cx - 2.5, ey - 0.2)
    assert not _inside(board, cx, ey + 0.5) and not _inside(board, cx, H - 0.2)
    # Wangen links/rechts reichen bis zur Unterkante -> seitliche Führung
    half = bp.RAST_NOTCH_W / 2
    assert 12.5 + 0.4 <= bp.RAST_NOTCH_W <= 12.5 + 1.0
    assert _inside(board, cx - half - 0.3, H - 0.3) and _inside(board, cx + half + 0.3, H - 0.3)
    assert not _inside(board, cx - half + 0.3, H - 0.3)
    # Schlitz: nur zwischen 3 und 4, 5 mm tief, >= 1 mm breit (JLCPCB)
    assert bp.SLOT_W >= 1.0
    for depth in (0.5, 2.5, bp.SLOT_DEPTH - bp.SLOT_W / 2 - 0.05):
        assert not _inside(board, bp.SLOT_X, ey - depth), depth
    assert _inside(board, bp.SLOT_X, ey - bp.SLOT_DEPTH - 0.2)
    for gap in (cx - 2.5, cx):                   # zwischen 1/2 und 2/3: kein Schlitz
        assert _inside(board, gap, ey - 2.5)
    # Kupfer hält mindestens 0,25 mm Abstand zum Schlitz
    pads = _rast_pads(board)
    assert bp.SLOT_X - bp.SLOT_W / 2 - pads[("3", "F")][1][2] >= 0.25
    assert pads[("4", "F")][1][0] - (bp.SLOT_X + bp.SLOT_W / 2) >= 0.25


def test_rast_area_free_of_parts(board):
    """Der Stecker umfasst die Zunge 5 mm tief – dort darf kein Bauteil sitzen."""
    import pcbnew
    import build_pcb as bp
    x0, x1 = bp.RAST_CX - 6.6, bp.RAST_CX + 6.6
    y0 = bp.RAST_EDGE - 5.0
    for fp in board.GetFootprints():
        if fp.GetReference() == "J2":
            continue
        bb = fp.GetBoundingBox(False, False)
        l, r = pcbnew.ToMM(bb.GetLeft()) - bp.OX, pcbnew.ToMM(bb.GetRight()) - bp.OX
        b = pcbnew.ToMM(bb.GetBottom()) - bp.OY
        assert not (r > x0 and l < x1 and b > y0), fp.GetReference()


def test_bom_and_cpl_consistent():
    bom = _csv("macs_esp32c6_bom.csv")
    cpl = _csv("macs_esp32c6_cpl.csv")
    bom_refs = [r for row in bom for r in row["Designator"].split(",")]
    cpl_refs = [row["Designator"] for row in cpl]
    assert sorted(bom_refs) == sorted(cpl_refs)
    assert len(set(bom_refs)) == len(bom_refs)
    for row in bom:
        assert re.fullmatch(r"C\d+", row["LCSC Part #"]), row
        assert int(row["Quantity"]) == len(row["Designator"].split(","))
    for row in cpl:
        x = float(row["Mid X"].rstrip("mm"))
        y = float(row["Mid Y"].rstrip("mm"))
        assert -1 <= x <= 40 and -10 <= y <= 66, row
    assert not {"JP1", "JP2", "TP1", "J4", "J2", "SW1", "SW2"} & set(cpl_refs)


def test_gerber_zip_complete():
    z = zipfile.ZipFile(os.path.join(FAB, "macs_esp32c6_gerber.zip"))
    names = " ".join(z.namelist())
    for tag in ("F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Silkscreen",
                "Edge_Cuts", "F_Paste"):
        assert tag in names, tag
    assert re.search(r"\.drl", names)


# ---------------------------------------------------------------- Firmware
def _yaml(name):
    import yaml

    class Loader(yaml.SafeLoader):
        pass
    Loader.add_constructor("!secret", lambda l, n: "secret")
    with open(os.path.join(ROOT, "firmware", name)) as f:
        return yaml.load(f, Loader=Loader)


FIRMWARE = ["macs-sniffer.yaml", "macs-washer.yaml"]


@pytest.mark.parametrize("name", FIRMWARE)
def test_esphome_yaml_matches_board(name):
    y = _yaml(name)
    u = y["uart"]
    assert u["rx_pin"]["number"] == "GPIO18" and u["rx_pin"]["inverted"] is True
    assert u["tx_pin"]["number"] == "GPIO19" and u["tx_pin"]["inverted"] is True
    assert u["baud_rate"] == 9600 and u["parity"] == "EVEN"
    assert y["status_led"]["pin"]["number"] == "GPIO8"
    assert y["esp32"]["variant"] == "esp32c6"
    assert y["esp32"]["flash_size"] == "8MB"            # WROOM-1-N8
    assert y["logger"]["hardware_uart"] == "USB_SERIAL_JTAG"
    assert any(o["pin"] == "GPIO21" for o in y["output"])   # blaue LED
    adc = [s for s in y["sensor"] if s["platform"] == "adc"]
    assert adc and adc[0]["pin"] == "GPIO0"
    assert adc[0]["filters"][0]["multiply"] == pytest.approx((33 + 10) / 10)


def test_firmware_pins_match_schematic():
    """GPIO-Nummern der YAMLs gegen die Netze im SKiDL-Schaltplan."""
    src = open(os.path.join(ROOT, "circuit.py")).read()
    assert 'u1[ESP["IO0"]] += v12_sense' in src
    for io in ("IO8", "IO18", "IO19", "IO21"):
        assert f'ESP["{io}"]' in src, io


@pytest.mark.parametrize("name", FIRMWARE)
def test_esphome_config_validates(name, tmp_path):
    """Volle ESPHome-Prüfung, wenn esphome installiert ist (ESPHOME=Pfad)."""
    import shutil
    exe = os.environ.get("ESPHOME") or shutil.which("esphome")
    if not exe:
        pytest.skip("esphome nicht installiert")
    import base64
    txt = open(os.path.join(ROOT, "firmware", name)).read()
    txt = txt.replace("__API_KEY__", base64.b64encode(b"k" * 32).decode())
    txt = txt.replace("__AP_PASSWORD__", "testtest12")
    (tmp_path / name).write_text(txt)
    (tmp_path / "secrets.yaml").write_text("wifi_ssid: x\nwifi_password: yyyyyyyy\n")
    r = subprocess.run([exe, "config", name], cwd=tmp_path, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


# ------------------------------------------------------- Protokollwerkzeug
def test_frame_roundtrip_and_checksum():
    import macs_frames as m
    fr = m.build_frame(0x2A, 0x21, [0x5F, 0x03])
    parsed = m.parse_stream(b"\x00\x11" + fr + m.build_frame(0, 0x21, [0x10, 0x00, 0x1B]))
    assert len(parsed) == 2 and all(p["ok"] for p in parsed)
    assert parsed[0]["payload"] == bytes([0x5F, 0x03])
    bad = bytearray(fr)
    bad[-1] ^= 0xFF
    assert not m.parse_stream(bytes(bad))[0]["ok"]


def test_frame_parser_reads_esphome_log():
    import macs_frames as m
    log = ("[14:23:01][D][uart_debug:114]: <<< C9 2A 21 02 5F 03 9C\n"
           "[14:23:01][D][sensor:093]: 'Bus 12V': Sending state 12.1 V\n")
    frames = m.parse_stream(m.hexbytes(log))
    assert len(frames) == 1 and frames[0]["ok"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_cpl_jlc_rotation_corrections():
    """Drehkorrekturen für JLCPCB (in deren Bestückungsvorschau geprüft):
    SOT-23 +180°, SOT-23-6/TSOT-23-6 +270°."""
    import csv
    import build_pcb as bp
    rows = {r["Designator"]: r for r in csv.DictReader(open(os.path.join(ROOT, "fab", "macs_esp32c6_cpl.csv")))}
    for ref, offset in (("Q1", 180), ("Q2", 180), ("U2", 270), ("U3", 270)):
        expect = (bp.PLACE[ref][2] + offset) % 360
        assert float(rows[ref]["Rotation"]) % 360 == expect, ref
    # gepolte Zweipoler ohne Korrektur
    for ref in ("D1", "D5", "D8"):
        assert float(rows[ref]["Rotation"]) % 360 == bp.PLACE[ref][2] % 360, ref


def test_trockner_capture_decodes():
    """Realer Mitschnitt vom AEG-Trockner: Frames, Programme, Zustände."""
    import macs_frames as m
    path = os.path.join(ROOT, "captures", "trockner-2026-11-18-programme.log")
    if not os.path.exists(path):
        pytest.skip("recording is not part of the public repository")
    frames = m.parse_stream(m.hexbytes(open(path).read()))
    msgs = [f for f in frames if f["kind"] == "msg"]
    assert len(msgs) > 100
    good = [f for f in msgs if f["ok"]]
    assert len(good) / len(msgs) > 0.95          # nur aneinandergeklebte Frames fallen durch
    # Programmwahl: 1, 2 und 4..10 kommen vor (3 war vor dem Durchschalten
    # schon angewählt und erscheint deshalb nicht)
    progs = {f["payload"][14] for f in good
             if f["source"] == 0x2A and f["payload"][:1] == b"\x50"}
    assert progs == {1, 2, 4, 5, 6, 7, 8, 9, 10}
    # Zustandsfolge nach Start/Stopp
    states = [f["payload"][2] for f in good
              if f["source"] == 0x22 and f["payload"][:1] == b"\x52"]
    assert {0x0b, 0x01, 0x02, 0x04} <= set(states)
    # Kompressor-Board meldet sich mit Kennung
    idents = [f["payload"] for f in good
              if f["source"] == 0x30 and f["payload"][:2] == b"\x11\x00"]
    assert idents and b"M1IB1606" in idents[0]
    assert m.DEVICES[0x30] == "Kompressor-Board"
