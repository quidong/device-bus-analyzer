"""
3D-Druck-Gehäuse für die MACS-ESP32-C6-Platine.

Liest Platinenumriss und Bauteilpositionen direkt aus der KiCad-Platine,
schreibt daraus enclosure/params.scad und rendert mit OpenSCAD:

  enclosure/macs_gehaeuse_unterteil.stl
  enclosure/macs_gehaeuse_deckel.stl

Konzept (ohne Befestigungslöcher in der Platine):
  * Unterteil: umlaufender Auflagesteg, auf dem die Platine liegt
  * Deckel: Steckrand (Reibschluss + Rastnasen) und Andrückrippen, die die
    Platine am Rand auf den Steg klemmen – nur dort, wo am Rand keine
    Bauteile sitzen (automatisch aus den Bauteilumrissen berechnet)
  * möglichst dicht: keine Öffnungen (USB nur zum ersten Flashen, Platine
    dafür herausnehmen), Labyrinth aus Steckrand + Nut/Feder, LED leuchtet
    durch eine dünne Restwand; einzige Öffnung ist die geteilte
    Kabeldurchführung (Hälfte im Unterteil, Hälfte im Deckel)
  * RAST-Stecker auf der Platinenzunge: Führungswände links/rechts (kein
    seitliches Verrutschen), Niederhalter im Deckel (kein Abheben), Kabel
    wird in der geteilten Durchführung geklemmt (Zugentlastung)
  * Kabelraum vor der Zunge, Oberseite eben (ohne Stützen druckbar)
  * 4 Magnete 5 x 5 mm in Laschen außen an den Längsseiten (wie BSH-Board),
    bündig mit der Unterseite; die Laschen liegen außerhalb des dichten Innenraums
  * 3 Lichtleiter mit dünner Restwand für Power-, Status- und Aktivitäts-LED
  * Antennenbereich des ESP32 bleibt frei von Metall/Schrauben

Koordinaten: x/y = Platine (Ursprung unten links, wie CPL), z = 0 an der
Platinen-Unterseite.

Aufruf: python3 enclosure/make_enclosure.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PCB = os.path.join(ROOT, "build", "macs_esp32c6.kicad_pcb")

# --------------------------------------------------------------- Parameter
P = {
    "board_t": 1.6,          # Platinendicke
    "wall": 2.0,             # Wandstärke
    "floor": 2.4,             # Boden-/Deckelstärke (2,0 unter der 0,4 mm tiefen Gravur)
    "gap": 0.3,              # Spiel Platine <-> Innenwand
    "below": 4.0,            # Freiraum unter der Platine (Stecker ragt 3,2 mm nach unten)
    "above": 4.6,            # Freiraum über der Platine (höchstes Teil 3,3 mm)
    "ledge": 2.0,            # Breite Auflagesteg
    "press_w": 1.7,           # Andrückrippen auf dem Platinenrand; reichen bis zur Wand (+Spiel) -> 2,0 mm
    "lip_h": 3.0,            # Höhe des Deckel-Steckrands
    "lip_t": 1.2,            # Stärke des Steckrands
    "fit": 0.15,             # Spiel Steckrand (Reibschluss)
    "snap": 0.35,            # Höhe der Rastnasen
    "antenna_clear": 2.7,    # Luft vor der Antennenspitze
    # --- Abdichtung: keine Öffnungen außer der Kabeldurchführung. Alle Wände
    #     >= 1,2 mm (Mindestwert JLC3DP für FDM); Dichtung über den 3 mm hohen
    #     Steckrand des Deckels (Labyrinth), keine dünne Nut/Feder mehr.
    "lip_t2": 2.0,           # Stärke Steckrand Deckel
    "lip_h2": 3.0,           # Höhe Steckrand (Überlappung mit der Wand)
    "min_wall": 2.0,         # Wandstärke tragender Teile (Kunde: 2 mm; JLC3DP min. 1,2)
    "led_skin": 1.2,         # Restwand über der LED: bewusst nur 1,2 mm (JLC-Minimum), sonst leuchtet sie nicht durch
    "led_tube_z": 4.6,       # Röhrchen beginnt an der Trennebene (= above), geht dort in die Deckelwand über
    "led_tube_d": 7.0,       # Lichtleiter-Röhrchen außen (Bohrung 3,0 -> Wand 2,0)
    # --- RAST-2.5-Direktstecker (Lumberg 3517 04 K01) auf der Platinenzunge
    "plug_w": 12.5,          # Breite Steckergehäuse (4-polig)
    "plug_on_board": 5.0,    # so weit umfasst der Stecker die Zunge
    "plug_out": 6.0,         # so weit ragt er über die Zungenkante hinaus
    "plug_z0": -3.2,         # Unterkante Stecker (z=0 = Platinenunterseite)
    "plug_above": 4.8,       # Oberkante Stecker über Platinenoberseite
    "guide_play": 0.3,       # seitliches Spiel Stecker <-> Führungswand
    "guide_t": 2.0,          # Stärke der Führungswände
    "hold_gap": 0.4,         # Luft Niederhalter <-> Steckeroberseite
    "chamber": 13.0,         # Kabelraum zwischen Zungenkante und Stirnwand
    # --- Haube, Kabel seitlich durch geteilte Durchführung (klemmt = Zugentlastung)
    "hood_above": 12.0,      # Innenhöhe des Deckels über der Platine
    "cable_d": 5.0,          # Kabeldurchmesser (LiYY 4x0,25 ≈ 4,9 mm)
    "cable_z": 7.5,          # Kabelmitte über Platinenoberseite
    "cable_fit": -0.3,       # negativ = Durchführung kleiner als Kabel -> klemmt
    # --- Magnete wie beim BSH-Board: Neodym 5 x 5 mm (supermagnete S-05-05-N)
    #     in Laschen außen an den Längsseiten, durchgehende Bohrung, Magnet
    #     bündig mit der Unterseite -> liegt direkt am Blech; Innenraum bleibt dicht
    "magnet_d": 5.0, "magnet_h": 5.0, "magnet_fit": 0.1, "magnet_web": 2.0,
    "lug_wall": 2.0,         # Wandstärke der Lasche um den Magneten
    "tab": False,            # Laschen mit Kabelbinder-Schlitz (bei Magneten nicht nötig)
}

# Kabelausgang mittig hinter dem RAST-Stecker J2
CABLE_EXITS = ["J2"]

# Magnetlaschen: Abstand der Laschen-Mitte von den Gehäuseenden (y), je Seite 2
MAGNET_INSET = 7.0

# LEDs mit Lichtleiter im Deckel (Power, Status, Aktivität)
LEDS = [("D8", "PWR"), ("D4", "ST"), ("D9", "ACT")]

# Bauteilhöhen über der Platinenoberseite (für Kollisionstest/Andrückrippen)
HEIGHTS = {"U1": 2.6, "J1": 3.3, "L1": 2.0, "C3": 1.4, "C5": 1.4, "SW1": 1.6,
           "SW2": 1.6, "default": 1.4}


def board_data():
    import pcbnew
    b = pcbnew.LoadBoard(PCB)
    org = b.GetDesignSettings().GetAuxOrigin()
    ox, oy = pcbnew.ToMM(org.x), pcbnew.ToMM(org.y)
    bb = b.GetBoardEdgesBoundingBox()
    lw = 0.1                                   # Strichbreite Edge.Cuts
    W = pcbnew.ToMM(bb.GetWidth()) - lw
    H = pcbnew.ToMM(bb.GetHeight()) - lw

    def tx(x):
        return round(pcbnew.ToMM(x) - ox, 3)

    def ty(y):
        return round(oy - pcbnew.ToMM(y), 3)

    parts = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if fp.GetLayer() != pcbnew.F_Cu:
            continue
        try:
            cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            x0, x1 = tx(cy.GetLeft()), tx(cy.GetRight())
            y0, y1 = ty(cy.GetBottom()), ty(cy.GetTop())
        except Exception:
            cbb = fp.GetBoundingBox(False, False)
            x0, x1 = tx(cbb.GetLeft()), tx(cbb.GetRight())
            y0, y1 = ty(cbb.GetBottom()), ty(cbb.GetTop())
        p = fp.GetPosition()
        parts[ref] = {"x": tx(p.x), "y": ty(p.y), "bbox": [x0, y0, x1, y1],
                      "h": HEIGHTS.get(ref, HEIGHTS["default"])}

    # USB-C: Vorderkante des Gehäuses aus der F.Fab-Kontur
    j1 = b.FindFootprintByReference("J1")
    fab = [g.GetBoundingBox() for g in j1.GraphicalItems() if g.GetLayer() == pcbnew.F_Fab]
    usb = {"front_x": min(tx(g.GetLeft()) for g in fab),
           "y0": min(ty(g.GetBottom()) for g in fab),
           "y1": max(ty(g.GetTop()) for g in fab)}
    # Antenne ragt über die Oberkante
    u1 = parts["U1"]["bbox"]
    # RAST-Steckkante: Ursprung des Footprints = Mitte an der Zungenkante
    sys.path.insert(0, ROOT)
    import build_pcb as bp
    rast = {"cx": parts["J2"]["x"], "edge": parts["J2"]["y"],
            "notch_w": bp.RAST_NOTCH_W, "slot_x": round(bp.SLOT_X, 3)}
    return {"W": round(W, 3), "H": round(H, 3), "parts": parts, "usb": usb,
            "antenna_top": round(u1[3], 3), "rast": rast}


def free_segments(parts, W, H, margin=0.3):
    """Abschnitte am Platinenrand (Breite press_w), auf denen keine Bauteile
    sitzen -> dort dürfen Andrückrippen aufliegen."""
    pw = P["press_w"]
    edges = {
        "left": (0, pw, "y", H), "right": (W - pw, W, "y", H),
        "bottom": (0, pw, "x", W), "top": (H - pw, H, "x", W),
    }
    segs = []
    for name, (a0, a1, axis, length) in edges.items():
        blocked = []
        for ref, p in parts.items():
            x0, y0, x1, y1 = p["bbox"]
            if axis == "y":        # Streifen x in [a0,a1]
                if x1 + margin > a0 and x0 - margin < a1:
                    blocked.append((y0 - margin, y1 + margin))
            else:                  # Streifen y in [a0,a1]
                if y1 + margin > a0 and y0 - margin < a1:
                    blocked.append((x0 - margin, x1 + margin))
        blocked.sort()
        pos, free = 1.5, []        # Ecken (Radius) auslassen
        for b0, b1 in blocked + [(length - 1.5, length)]:
            if b0 - pos >= 3.0:
                free.append((round(pos, 2), round(b0, 2)))
            pos = max(pos, b1)
        for s0, s1 in free:
            if axis == "y":
                segs.append([a0, s0, a1, s1])
            else:
                segs.append([s0, a0, s1, a1])
    return segs


def write_params(d):
    parts = d["parts"]
    segs = free_segments(parts, d["W"], d["H"])
    lines = ["// automatisch erzeugt von make_enclosure.py – nicht von Hand ändern"]
    for k, v in P.items():
        lines.append(f"{k} = {str(v).lower() if isinstance(v, bool) else v};")
    lines += [
        f"W = {d['W']};", f"H = {d['H']};",
        f"antenna_top = {d['antenna_top']};",
        f"rast_cx = {d['rast']['cx']}; rast_edge = {d['rast']['edge']};",
        "leds = [" + ", ".join(f"[{parts[r]['x']}, {parts[r]['y']}]" for r, _ in LEDS) + "];",
        "led_names = [" + ", ".join(f'"{n}"' for _, n in LEDS) + "];",
        "press = [" + ", ".join(f"[{a},{b},{c},{e}]" for a, b, c, e in segs) + "];",
        "cable_x = [" + ", ".join(f"{parts[r]['x']:.3f}" for r in CABLE_EXITS) + "];",
        f"usb_y0 = {d['usb']['y0']}; usb_y1 = {d['usb']['y1']};",
        f"magnet_inset = {MAGNET_INSET};",
    ]
    with open(os.path.join(HERE, "params.scad"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "board.json"), "w") as f:
        json.dump({**d, "press": segs, "P": P, "cable_exits": CABLE_EXITS,
                   "magnet_inset": MAGNET_INSET, "leds": [r for r, _ in LEDS]}, f, indent=1)
    return segs


def render():
    for part in ("unterteil", "deckel", "deckel_montiert"):
        out = os.path.join(HERE, f"macs_gehaeuse_{part}.stl")
        if part == "deckel_montiert":
            out = os.path.join(HERE, "test", "deckel_montiert.stl")
            os.makedirs(os.path.dirname(out), exist_ok=True)
        r = subprocess.run(["openscad", "-o", out, "-D", f'part="{part}"',
                            os.path.join(HERE, "gehaeuse.scad")],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            sys.exit(f"OpenSCAD-Fehler ({part}):\n{r.stderr[-2000:]}")
        print("geschrieben:", out)


if __name__ == "__main__":
    d = board_data()
    segs = write_params(d)
    print(f"Platine {d['W']} x {d['H']} mm, Antenne bis y={d['antenna_top']}, "
          f"{len(segs)} Andrückrippen")
    render()
