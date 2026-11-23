"""
Baut die Leiterplatte MACS-ESP32-C6 aus der Netzliste:

  1. Netzliste -> .kicad_pcb mit allen Footprints (kinet2pcb)
  2. Platzierung, Platinenumriss, Netzklassen, Masseflächen
  3. Export Specctra-DSN -> Freerouting (Autorouter) -> SES zurück
  4. Zonen füllen, speichern

Aufruf:  python3 build_pcb.py [--no-route]
"""
import os
import subprocess
import sys

import pcbnew
import kinet2pcb

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
NET = os.path.join(BUILD, "macs_esp32c6.net")
PCB = os.path.join(BUILD, "macs_esp32c6.kicad_pcb")
DSN = os.path.join(BUILD, "macs_esp32c6.dsn")
SES = os.path.join(BUILD, "macs_esp32c6.ses")
FREEROUTING = "/opt/freerouting/freerouting-2.1.0.jar"

FP_DIRS = ["/usr/share/kicad/footprints", os.path.join(HERE, "lib")]

# Platine (mm) – Ursprung oben links, Versatz auf die KiCad-Seite
OX, OY = 100.0, 100.0
W, H = 30.0, 54.0

# --------------------------------------------------------------------------
# Platzierung: Referenz -> (x, y, Drehung°, Seite)   (Koordinaten auf Platine)
# --------------------------------------------------------------------------
PLACE = {
    # WROOM-1 oben mittig, Antennenteil (lokal y -15,75 … -9,75) ragt über die Oberkante
    "U1": (15.0, 9.75, 0),
    # --- links neben dem Modul: Entkopplung 3V3 (Pin 2), EN (Pin 3), Status-LED (IO8, Pin 10)
    "C7": (3.6, 2.8, 90), "C8": (1.8, 2.8, 90),
    "R6": (3.6, 6.0, 90), "C9": (1.8, 6.0, 90),
    "D4": (2.4, 11.6, 90), "R8": (4.2, 11.6, 90),
    # --- rechts neben dem Modul: Power- und Aktivitäts-LED, BOOT-Pull-up (Pin 15)
    "D8": (27.6, 3.0, 90), "R17": (25.8, 3.0, 90),
    "D9": (27.6, 9.0, 90), "R18": (25.8, 9.0, 90),
    "R7": (25.8, 15.6, 90),
    # --- unter dem Modul (wie v1.1-MINI, verschoben)
    "J1": (3.7, 26.0, 270),
    "U3": (12.0, 26.0, 90),
    "R9": (11.0, 21.8, 0),
    "R10": (11.0, 30.2, 0),
    "R11": (16.4, 22.0, 0),
    "R12": (16.4, 23.4, 0),
    "C10": (16.4, 24.8, 0),
    "R13": (19.6, 22.0, 0),
    "R14": (19.6, 23.4, 0),
    "Q1": (20.6, 26.2, 0),
    "R15": (23.8, 24.2, 90),
    "Q2": (25.6, 28.6, 0),
    "R16": (22.2, 30.6, 0),
    "D2": (5.2, 33.2, 180),
    "D3": (5.2, 35.8, 180),
    "D1": (5.2, 38.4, 180),
    "JP2": (10.4, 36.6, 90),
    "C1": (12.8, 37.0, 90),
    "C2": (14.1, 37.0, 90),
    "U2": (16.4, 33.6, 0),
    "C4": (16.4, 31.0, 0),
    "L1": (20.0, 34.6, 90),
    "C3": (23.4, 34.8, 90),
    "C5": (25.6, 34.8, 90),
    "R4": (16.4, 39.0, 0),
    "R5": (16.4, 40.4, 0),
    "C11": (16.4, 41.8, 0),
    "D5": (5.6, 41.4, 0),
    "D7": (12.2, 41.6, 90),
    "D6": (20.6, 41.6, 90),
    "SW2": (4.4, 47.2, 0),
    "SW1": (25.6, 47.2, 0),
    "TP1": (2.8, 51.2, 0),
    "TP2": (5.0, 51.2, 0),
    "TP4": (7.2, 51.2, 0),
    "TP3": (22.8, 51.2, 0),
    "TP5": (25.0, 51.2, 0),
    "TP6": (27.2, 51.2, 0),
    "TP7": (25.0, 43.4, 0),
    "J2": (15.0, 51.5, 0),
}

# RAST-Steckkante: Aussparung in der Unterkante, darin die Platinenzunge mit
# den Kontakten; seitliche Wangen führen den Stecker (wie BSH-Board).
RAST_CX = PLACE["J2"][0]       # Mitte Stecker
RAST_EDGE = PLACE["J2"][1]     # Vorderkante der Zunge
RAST_NOTCH_W = 13.2            # Stecker 12,5 mm + Spiel, Fräserradius 0,5 in den Ecken
SLOT_X = RAST_CX + 2.5         # Codierschlitz zwischen Kontakt 3 und 4
SLOT_W = 1.0                   # JLCPCB: gefräste Schlitze ab 1,0 mm
SLOT_DEPTH = 5.0               # so tief wie der Stecker die Platine umfasst
SLOT_CHAMFER = 0.3             # Einführschräge je Seite


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def add_line(board, x1, y1, x2, y2, layer, width=0.1):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pt(x1, y1))
    seg.SetEnd(pt(x2, y2))
    seg.SetLayer(layer)
    seg.SetWidth(mm(width))
    board.Add(seg)


def add_outline(board, r=1.0):
    """Rechteck mit abgerundeten Ecken auf Edge.Cuts, unten mit Aussparung für
    den RAST-Stecker und Codierschlitz in der Zunge."""
    import math
    e = pcbnew.Edge_Cuts
    nx0, nx1 = RAST_CX - RAST_NOTCH_W / 2, RAST_CX + RAST_NOTCH_W / 2
    sy = RAST_EDGE
    sl, sr = SLOT_X - SLOT_W / 2, SLOT_X + SLOT_W / 2
    top = sy - SLOT_DEPTH + SLOT_W / 2          # Mittelpunkt der Rundung oben
    add_line(board, r, 0, W - r, 0, e)
    add_line(board, W, r, W, H - r, e)
    add_line(board, 0, H - r, 0, r, e)
    # Unterkante mit Aussparung und Schlitz (von rechts nach links)
    path = [(W - r, H), (nx1, H), (nx1, sy), (sr + SLOT_CHAMFER, sy), (sr, sy - 1.0),
            (sr, top)]
    for a, b in zip(path, path[1:]):
        add_line(board, *a, *b, e)
    arc = pcbnew.PCB_SHAPE(board)
    arc.SetShape(pcbnew.SHAPE_T_ARC)
    arc.SetArcGeometry(pt(sr, top), pt(SLOT_X, top - SLOT_W / 2), pt(sl, top))
    arc.SetLayer(e)
    arc.SetWidth(mm(0.1))
    board.Add(arc)
    path = [(sl, top), (sl, sy - 1.0), (sl - SLOT_CHAMFER, sy), (nx0, sy), (nx0, H), (r, H)]
    for a, b in zip(path, path[1:]):
        add_line(board, *a, *b, e)
    for cx, cy, sa in ((r, r, 180), (W - r, r, 270), (W - r, H - r, 0), (r, H - r, 90)):
        arc = pcbnew.PCB_SHAPE(board)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetCenter(pt(cx, cy))
        a = math.radians(sa)
        arc.SetStart(pt(cx + r * math.cos(a), cy + r * math.sin(a)))
        arc.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        arc.SetLayer(e)
        arc.SetWidth(mm(0.1))
        board.Add(arc)


def add_zone(board, net_name, layer, clearance=0.3, keepout_y=None):
    net = board.FindNet(net_name)
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetLocalClearance(mm(clearance))
    zone.SetMinThickness(mm(0.25))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    zone.SetThermalReliefGap(mm(0.3))
    zone.SetThermalReliefSpokeWidth(mm(0.4))
    poly = zone.Outline()
    poly.NewOutline()
    y0 = keepout_y if keepout_y is not None else 0.3
    for x, y in ((0.3, y0), (W - 0.3, y0), (W - 0.3, H - 0.3), (0.3, H - 0.3)):
        poly.Append(mm(OX + x), mm(OY + y))
    board.Add(zone)
    return zone


def add_edge_keepouts(board, band=0.3):
    """Sperrzonen (keine Leiterbahnen/Vias) entlang Steckeraussparung und
    Codierschlitz: Freerouting kennt nur 0,15 mm Abstand, die Kante braucht
    0,2 mm. Kupferflächen und Pads sind dort weiter erlaubt."""
    def rule_area(pts):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowCopperPour(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        poly = z.Outline()
        poly.NewOutline()
        for x, y in pts:
            poly.Append(mm(OX + x), mm(OY + y))
        board.Add(z)
    nx0, nx1 = RAST_CX - RAST_NOTCH_W / 2 - band, RAST_CX + RAST_NOTCH_W / 2 + band
    rule_area([(nx0, RAST_EDGE - band), (nx1, RAST_EDGE - band), (nx1, H), (nx0, H)])
    sx0, sx1 = SLOT_X - SLOT_W / 2 - 0.25, SLOT_X + SLOT_W / 2 + 0.25
    top = RAST_EDGE - SLOT_DEPTH - band
    rule_area([(sx0, top), (sx1, top), (sx1, RAST_EDGE), (sx0, RAST_EDGE)])


def add_text(board, text, x, y, layer, size=1.0, thick=0.15, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    if angle:
        t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if layer in (pcbnew.B_SilkS, pcbnew.B_Cu):
        t.SetMirrored(True)          # von unten lesbar
    board.Add(t)


def setup_rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_MinClearance = mm(0.15)          # JLCPCB kann 0,1 mm; 0,15 mit Reserve
    ds.m_CopperEdgeClearance = mm(0.2)    # JLCPCB-Minimum
    ds.SetCopperLayerCount(2)

    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(mm(0.15))
    nc.SetTrackWidth(mm(0.2))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))

    power = pcbnew.NETCLASS("Power")
    power.SetClearance(mm(0.15))    # USB-C-Pads haben selbst nur 0,2 mm Abstand
    power.SetTrackWidth(mm(0.35))   # Strom < 0,3 A
    power.SetViaDiameter(mm(0.8))
    power.SetViaDrill(mm(0.4))
    ds.m_NetSettings.m_NetClasses["Power"] = power
    return power


def assign_power_class(board):
    """Netzklasse 'Power' (0,4 mm) für Versorgungsnetze."""
    ds = board.GetDesignSettings()
    power = ds.m_NetSettings.m_NetClasses["Power"]
    for n in POWER_NETS:
        net = board.FindNet(n)
        if net is None:
            raise SystemExit(f"Netz fehlt: {n}")
        net.SetNetClass(power)


def copy_fields(board):
    """Felder (LCSC, MPN, DNP) aus der Netzliste an die Footprints hängen –
    kinet2pcb überträgt sie nicht."""
    import re
    txt = open(NET).read()
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\(libsource', txt, re.S):
        ref, body = m.group(1), m.group(2)
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            continue
        for name, val in re.findall(r'\(field\s+\(name "([^"]+)"\)\s*"([^"]*)"\)', body):
            if name in ("LCSC", "MPN", "DNP"):
                fp.SetProperty(name, val)
        if 'name "DNP") "1"' in body:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM
                             | pcbnew.FP_EXCLUDE_FROM_POS_FILES)


def place(board):
    missing = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in PLACE:
            missing.append(ref)
            continue
        x, y, rot = PLACE[ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        # Referenz klein und lesbar; bei Kleinteilen nur auf F.Fab
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.12))
        fp.Reference().SetLayer(pcbnew.F_Fab)       # zu eng für Bestückungsdruck
        fp.Value().SetVisible(False)
        if ref == "J1":   # Schirm-Pins massiv an GND (Thermals hätten zu wenig Stege)
            for pad in fp.Pads():
                if pad.GetNumber() == "S1":
                    pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    if missing:
        raise SystemExit(f"Nicht platziert: {missing}")


def strip_antenna_keepout(board):
    """Die Antenne ragt über den Rand hinaus – Keepout-Zone im Footprint
    bleibt, liegt aber außerhalb der Platine (keine Auswirkung)."""
    return


POWER_NETS = ("+12V_BUS", "+5V_BUS", "VBUS", "V12_D", "V5_D", "VIN", "+3V3",
              "SW")


def patch_dsn_classes(path):
    """KiCad 7 exportiert Netzklassen nur aus dem Projekt – Power-Netze hier
    direkt in die DSN-Klasse 'Power' (0,6 mm) verschieben."""
    import re
    s = open(path).read()
    m = re.search(r'\(class kicad_default ""(.*?)\(circuit', s, re.S)
    names = m.group(1).split()
    keep = [n for n in names if n not in POWER_NETS]
    moved = [n for n in names if n in POWER_NETS]
    s = s[:m.start(1)] + " " + " ".join(keep) + "\n      " + s[m.end(1):]
    s = s.replace("(class Power\n", "(class Power " + " ".join(moved) + "\n", 1)
    open(path, "w").write(s)
    return moved


def import_ses(board, path):
    """Eigener SES-Import (pcbnew.ImportSpecctraSES braucht in KiCad 7 die GUI)."""
    import re
    txt = open(path).read()
    res = int(re.search(r"\(resolution um (\d+)\)", txt).group(1))
    to_mm = lambda v: float(v) / res / 1000.0  # noqa: E731
    layer_ids = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    net_out = txt[txt.index("(network_out"):]
    vias, tracks = 0, 0
    for nm in re.finditer(r"\(net (\"[^\"]+\"|\S+)(.*?)(?=\n      \(net |\n    \)\n)",
                          net_out, re.S):
        name = nm.group(1).strip('"')
        body = nm.group(2)
        net = board.FindNet(name)
        if net is None:
            raise SystemExit(f"SES: unbekanntes Netz {name}")
        for pm in re.finditer(r"\(path (\S+) (\d+)\s+([-\d\s]+)\)", body):
            layer = layer_ids[pm.group(1)]
            width = to_mm(pm.group(2))
            nums = [int(v) for v in pm.group(3).split()]
            pts = list(zip(nums[0::2], nums[1::2]))
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(mm(to_mm(x1)), mm(-to_mm(y1))))
                t.SetEnd(pcbnew.VECTOR2I(mm(to_mm(x2)), mm(-to_mm(y2))))
                t.SetWidth(mm(width))
                t.SetLayer(layer)
                t.SetNet(net)
                board.Add(t)
                tracks += 1
        for vm in re.finditer(r'\(via "Via\[0-1\]_(\d+):(\d+)_um" (-?\d+) (-?\d+)', body):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(to_mm(vm.group(3))), mm(-to_mm(vm.group(4)))))
            v.SetWidth(mm(int(vm.group(1)) / 1000.0))
            v.SetDrill(mm(int(vm.group(2)) / 1000.0))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            board.Add(v)
            vias += 1
    print(f"SES importiert: {tracks} Leiterbahnsegmente, {vias} Vias")


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def route(board):
    """Freerouting mit mehreren Einstellungen versuchen, bis KiCad selbst
    keine offenen Verbindungen mehr findet (der Optimierer von Freerouting
    verliert bei mehreren Threads gelegentlich Leiterbahnstücke)."""
    pcbnew.ExportSpecctraDSN(board, DSN)
    moved = patch_dsn_classes(DSN)
    print("Power-Klasse:", moved)
    # Freerouting ist nicht deterministisch -> mehrere Versuche
    attempts = [["-mp", "100", "-mt", "1", "-oit", "0.5"]] * int(os.environ.get("ROUTE_ATTEMPTS", "6"))
    log_all = ""
    for extra in attempts:
        if os.path.exists(SES):
            os.remove(SES)
        cmd = ["java", "-jar", FREEROUTING, "-de", DSN, "-do", SES,
               *extra, "--gui.enabled=false"]
        print("Freerouting:", " ".join(extra))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        log_all += f"\n===== {' '.join(extra)} =====\n" + r.stdout + r.stderr
        if not os.path.exists(SES):
            continue
        import_ses(board, SES)
        n = unconnected(board)
        print(f"  offene Verbindungen nach Import: {n}")
        if n == 0:
            import shutil
            shutil.copy(SES, SES + ".keep")   # gutes Routing aufbewahren
            break
        for t in list(board.GetTracks()):
            board.Remove(t)
    with open(os.path.join(BUILD, "freerouting.log"), "w") as f:
        f.write(log_all)
    if unconnected(board):
        raise SystemExit("Routing unvollständig – Platzierung anpassen")


def remove_gnd_near_edge(board, clearance=0.2):
    """Freerouting kennt nur einen Abstand für alles (0,15 mm); GND-Stücke,
    die näher als 0,2 mm an die Platinenkante kommen, werden gelöscht – die
    Massefläche übernimmt die Verbindung (wird danach geprüft)."""
    poly = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(poly)
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetNetname() != "GND":
            continue
        inner = poly.CloneDropTriangulation() if hasattr(poly, "CloneDropTriangulation") else pcbnew.SHAPE_POLY_SET(poly)
        half = (t.GetWidth() if t.Type() == pcbnew.PCB_TRACE_T else t.GetWidth()) / 2
        inner.Deflate(int(mm(clearance) + half), 16)
        pts = [t.GetStart(), t.GetEnd()]
        if t.Type() == pcbnew.PCB_TRACE_T:
            a, b = t.GetStart(), t.GetEnd()
            pts += [pcbnew.VECTOR2I(int(a.x + (b.x - a.x) * k / 8), int(a.y + (b.y - a.y) * k / 8))
                    for k in range(1, 8)]
        if not all(inner.Contains(p) for p in pts):
            board.Remove(t)
            removed += 1
    print("GND-Stücke an der Kante entfernt:", removed)


def remove_dangling(board):
    """Lose Leiterbahnenden (Router-Reste) entfernen – mit KiCads eigener
    Prüfung, wiederholt bis nichts mehr übrig ist."""
    removed = 0
    while True:
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        dangling = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA"
                    and conn.TestTrackEndpointDangling(t, False)]
        if not dangling:
            break
        for t in dangling:
            board.Remove(t)
            removed += 1
    print(f"Lose Leiterbahnstücke entfernt: {removed}")


def add_stitching_vias(board, pitch=3.5, via_d=0.6, drill=0.3, clearance=0.3):
    """GND-Durchkontaktierungen im Raster überall dort, wo Platz ist –
    verbindet die Masseflächen beider Lagen niederohmig."""
    import math
    gnd = board.FindNet("GND")
    r = via_d / 2
    obstacles = []
    for t in board.GetTracks():
        if t.GetNetCode() == gnd.GetNetCode():
            continue
        w = pcbnew.ToMM(t.GetWidth()) / 2
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            obstacles.append(("c", pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), w))
        else:
            a, b = t.GetStart(), t.GetEnd()
            obstacles.append(("s", pcbnew.ToMM(a.x), pcbnew.ToMM(a.y),
                              pcbnew.ToMM(b.x), pcbnew.ToMM(b.y), w))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd.GetNetCode() and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                continue
            bb = pad.GetBoundingBox()
            obstacles.append(("b", pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                              pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
        # keine Vias unter Bauteilen mit Gehäuse auf der Platine (Taster, Stecker)
        if fp.GetReference()[0] in "JS":
            cb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            obstacles.append(("b", pcbnew.ToMM(cb.GetLeft()), pcbnew.ToMM(cb.GetTop()),
                              pcbnew.ToMM(cb.GetRight()), pcbnew.ToMM(cb.GetBottom())))

    def seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def free(px, py):
        for o in obstacles:
            if o[0] == "c" and math.hypot(px - o[1], py - o[2]) < r + o[3] + clearance:
                return False
            if o[0] == "s" and seg_dist(px, py, *o[1:5]) < r + o[5] + clearance:
                return False
            if o[0] == "b" and (o[1] - r - clearance < px < o[3] + r + clearance and
                                o[2] - r - clearance < py < o[4] + r + clearance):
                return False
        return True

    placed = 0
    y = 1.5
    while y < H - 1.2:
        x = 1.5
        while x < W - 1.2:
            px, py = OX + x, OY + y
            if free(px, py):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(mm(px), mm(py)))
                v.SetWidth(mm(via_d))
                v.SetDrill(mm(drill))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(gnd)
                board.Add(v)
                obstacles.append(("c", px, py, r))
                placed += 1
            x += pitch
        y += pitch
    print(f"GND-Stitching-Vias: {placed}")


def write_project_files():
    """Projektdatei mit den Entwurfsregeln (JLCPCB 2-Lagen) und Netzklassen
    schreiben – KiCad liest Regeln aus der .kicad_pro, nicht aus der .kicad_pcb."""
    import json
    pro = os.path.splitext(PCB)[0] + ".kicad_pro"
    d = json.load(open(pro)) if os.path.exists(pro) else {"meta": {"version": 1}}
    d.setdefault("meta", {})["filename"] = os.path.basename(pro)
    ds = d.setdefault("board", {}).setdefault("design_settings", {})
    ds.setdefault("rules", {}).update({
        "min_clearance": 0.15, "min_copper_edge_clearance": 0.2,
        "min_track_width": 0.2, "min_via_diameter": 0.5,
        "min_via_annular_width": 0.1, "min_through_hole_diameter": 0.3,
        "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
        "min_text_height": 0.8, "min_text_thickness": 0.12,
        "min_resolved_spokes": 1,
    })
    base = {"bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3,
            "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6}
    ns = d.setdefault("net_settings", {})
    ns["classes"] = [
        dict(base, name="Default", clearance=0.15, track_width=0.2,
             via_diameter=0.6, via_drill=0.3),
        dict(base, name="Power", clearance=0.15, track_width=0.35,
             via_diameter=0.8, via_drill=0.4),
    ]
    ns["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
    ns.setdefault("meta", {"version": 3})
    with open(pro, "w") as f:
        json.dump(d, f, indent=2)
    lib = os.path.relpath(os.path.join(HERE, "lib"), BUILD)
    with open(os.path.join(BUILD, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (lib (name "macs")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{lib}/macs.pretty")(options "")(descr "Projektbibliothek"))\n)\n')
    with open(os.path.join(BUILD, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "macs")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{lib}/macs.kicad_sym")(options "")(descr "Projektbibliothek"))\n)\n')


def main():
    do_route = "--no-route" not in sys.argv
    os.makedirs(BUILD, exist_ok=True)
    for f in (PCB, DSN) if "--use-ses" in sys.argv else (PCB, DSN, SES):
        if os.path.exists(f):
            os.remove(f)
    kinet2pcb.kinet2pcb(NET, PCB, FP_DIRS)
    board = pcbnew.LoadBoard(PCB)

    setup_rules(board)
    assign_power_class(board)
    place(board)
    copy_fields(board)
    add_outline(board)
    # Hilfsursprung unten links -> Gerber, Bohrdaten und CPL im selben System
    board.GetDesignSettings().SetAuxOrigin(pt(0, H))

    # Beschriftung
    add_text(board, "MACS-C6 v1.2", 15.0, 28.6, pcbnew.F_SilkS, 0.8, 0.13)
    add_text(board, "1", RAST_CX - 3.75, 44.2, pcbnew.F_SilkS, 0.8, 0.12)
    add_text(board, "4", RAST_CX + 3.85, 44.2, pcbnew.F_SilkS, 0.8, 0.12)
    add_text(board, "RST", 4.4, 49.4, pcbnew.F_SilkS, 0.8, 0.12)
    add_text(board, "BOOT", 25.6, 49.4, pcbnew.F_SilkS, 0.8, 0.12)
    add_text(board, "JP2", 10.4, 39.6, pcbnew.F_SilkS, 0.8, 0.12)
    for txt, y in (("!! NETZPOTENZIAL MOEGLICH !!", 6.0),
                   ("USB NIE zusammen mit", 9.0), ("angeschlossenem Geraet!", 10.6),
                   ("MACS 1=12V 2=5V 3=D 4=GND", 14.0),
                   ("RX=IO18 TX=IO19 8E1 inv.", 16.0),
                   ("LED: PWR / ST=IO8 / ACT=IO21", 18.0),
                   ("JP2: 1-2=12V  2-3=5V", 20.0),
                   ("TP: DATA GND 5V | 3V3 IO2 IO3", 30.0)):
        add_text(board, txt, 15.0, y + 8.0, pcbnew.B_SilkS, 0.8, 0.12)

    add_edge_keepouts(board)
    if "--use-ses" in sys.argv and os.path.exists(SES + ".keep"):
        import_ses(board, SES + ".keep")          # vorhandenes Routing übernehmen
    elif do_route:
        route(board)

    # Masseflächen beidseitig (nach dem Routing, damit der Router frei ist)
    remove_gnd_near_edge(board)
    remove_dangling(board)
    add_stitching_vias(board)
    add_zone(board, "GND", pcbnew.F_Cu)
    add_zone(board, "GND", pcbnew.B_Cu)
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.BuildConnectivity()
    if unconnected(board) and (do_route or "--use-ses" in sys.argv):
        raise SystemExit(f"Offene Verbindungen nach Zonenfüllung: {unconnected(board)}")

    board.Save(PCB)
    write_project_files()
    print("Gespeichert:", PCB)


if __name__ == "__main__":
    main()
