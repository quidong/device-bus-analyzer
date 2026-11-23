"""
Erzeugt lib/macs.pretty/RAST25_Direkt_1x04_K34.kicad_mod

RAST-2.5-Direktsteckkante, 4-polig, Codierung zwischen Kontakt 3 und 4
(passend zu Lumberg 3517 04 K01 / Electrolux-Trockner).
Vorbild: Bouni/BSH-Board (Würth WR-RAST, 3-polig), auf 4 Pole erweitert.

Ursprung = Mitte des Steckers an der Aussparungskante (dort endet die
Platinenzunge). Kontakte auf beiden Seiten (F.Cu und B.Cu), über eine
Durchkontaktierung am inneren Ende verbunden – so ist es egal, auf welcher
Seite die Federn des Steckers anliegen. Keine Lötpaste auf den Kontakten.
Die Kontur (Aussparung + Codierschlitz) zeichnet build_pcb.py in Edge.Cuts.
"""
import os

PITCH = 2.5
PAD_L = 5.0            # Kontaktlänge (Stecker umfasst 5 mm der Platine)
PAD_EDGE = 1.0         # Abstand Kontaktende <-> Platinenkante
PAD_W = 1.3
SLOT_W = 1.0           # JLCPCB-Minimum für gefräste Schlitze
CLR = 0.3              # Kupfer <-> Schlitz
VIA_D, VIA_DRILL = 0.8, 0.4


def pads():
    """(nummer, x, breite) – Pad 3 und 4 sind zum Schlitz hin gekürzt."""
    xs = [(-1.5 + i) * PITCH for i in range(4)]
    slot_x = (xs[2] + xs[3]) / 2
    out = []
    for n, x in enumerate(xs, start=1):
        if n in (3, 4):
            inner = slot_x - SLOT_W / 2 - CLR if n == 3 else slot_x + SLOT_W / 2 + CLR
            outer = x - PAD_W / 2 if n == 3 else x + PAD_W / 2
            lo, hi = sorted((inner, outer))
            out.append((n, (lo + hi) / 2, hi - lo))
        else:
            out.append((n, x, PAD_W))
    return out, slot_x


def main():
    ps, slot_x = pads()
    py = -(PAD_EDGE + PAD_L / 2)
    vy = -(PAD_EDGE + PAD_L) - VIA_D / 2 + 0.4   # überlappt das innere Padende
    L = ['(footprint "RAST25_Direkt_1x04_K34" (version 20221018) (generator pcbnew)',
         '  (layer "F.Cu")',
         '  (descr "RAST 2.5 Direktsteckkante 4-polig, Codierung zwischen 3 und 4 '
         '(Lumberg 3517 04 K01), Kontakte beidseitig")',
         '  (tags "RAST 2.5 direct mating edge")',
         '  (attr smd exclude_from_pos_files exclude_from_bom)',
         '  (fp_text reference "REF**" (at 0 -8.2) (layer "F.SilkS") '
         '(effects (font (size 0.9 0.9) (thickness 0.15))))',
         '  (fp_text value "RAST25_4p_K34" (at 0 4) (layer "F.Fab") '
         '(effects (font (size 0.8 0.8) (thickness 0.12))))']
    # Steckerkörper (Fab) und Courtyard
    L.append('  (fp_rect (start -6.25 -6.0) (end 6.25 6.0) (stroke (width 0.1) (type default)) '
             '(fill none) (layer "F.Fab"))')
    L.append('  (fp_rect (start -6.6 -6.4) (end 6.6 6.5) (stroke (width 0.05) (type default)) '
             '(fill none) (layer "F.CrtYd"))')
    for n, x, w in ps:
        for side in ("F", "B"):
            L.append(f'  (pad "{n}" smd rect (at {x:.3f} {py:.3f}) (size {w:.3f} {PAD_L}) '
                     f'(layers "{side}.Cu" "{side}.Mask"))')
        L.append(f'  (pad "{n}" thru_hole circle (at {x:.3f} {vy:.3f}) (size {VIA_D} {VIA_D}) '
                 f'(drill {VIA_DRILL}) (layers "*.Cu" "*.Mask"))')
    L.append(')')
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "lib", "macs.pretty", "RAST25_Direkt_1x04_K34.kicad_mod")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    print("geschrieben:", path, "Schlitz bei x =", slot_x)


if __name__ == "__main__":
    main()
