"""
Erzeugt die JLCPCB-Fertigungsdaten aus build/macs_esp32c6.kicad_pcb:

  fab/macs_esp32c6_gerber.zip   Gerber + Excellon-Bohrdaten
  fab/macs_esp32c6_bom.csv      Stückliste (JLC-Format, mit LCSC-Nummern)
  fab/macs_esp32c6_cpl.csv      Bestückungsdaten (Pick & Place)
  fab/macs_esp32c6_schematic.pdf, fab/macs_esp32c6_pcb.pdf

Aufruf: python3 make_fab.py
"""
import csv
import os
import shutil
import subprocess
import zipfile
from collections import OrderedDict

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "build", "macs_esp32c6.kicad_pcb")
SCH = os.path.join(HERE, "build", "macs_esp32c6.kicad_sch")
FAB = os.path.join(HERE, "fab")
GERBER_DIR = os.path.join(FAB, "gerber")

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# Teile ohne Bestückung durch JLC (reines Kupfer oder Handlötung)
NO_ASSEMBLY_PREFIX = ("JP", "TP")


# Drehkorrektur KiCad -> JLCPCB-Bauteilmodell, in der JLC-Bestückungsvorschau
# geprüft (rosa Punkt = Pin 1 des JLC-Modells). Footprint-Name -> Offset in Grad.
JLC_ROTATION = {
    "SOT-23": 180,        # Transistoren Q1/Q2: JLC-Modell liegt 180° verdreht
    "SOT-23-6": 270,      # USBLC6: JLC-Modell 90° verdreht
    "TSOT-23-6": 270,     # AP63203: JLC-Modell 90° verdreht
}


def jlc_rotation_offset(fp):
    return JLC_ROTATION.get(fp.GetFPID().GetLibItemName().wx_str(), 0)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Fehler: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def gerbers():
    shutil.rmtree(GERBER_DIR, ignore_errors=True)
    os.makedirs(GERBER_DIR)
    run(["kicad-cli", "pcb", "export", "gerbers", "-o", GERBER_DIR + "/",
         "--layers", LAYERS, "--subtract-soldermask", "--no-netlist",
         "--use-drill-file-origin", PCB])
    run(["kicad-cli", "pcb", "export", "drill", "-o", GERBER_DIR + "/",
         "--format", "excellon", "--excellon-units", "mm", "--drill-origin", "plot",
         "--excellon-separate-th",
         PCB])
    zpath = os.path.join(FAB, "macs_esp32c6_gerber.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(GERBER_DIR)):
            z.write(os.path.join(GERBER_DIR, f), f)
    return zpath


def fp_field(fp, name):
    if hasattr(fp, "HasFieldByName"):            # KiCad 8+
        return fp.GetFieldText(name) if fp.HasFieldByName(name) else ""
    return fp.GetProperty(name) if fp.HasProperty(name) else ""   # KiCad 7


def parts(board):
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        out.append({
            "ref": ref,
            "value": fp.GetValue(),
            "footprint": fp.GetFPID().GetLibItemName().wx_str(),
            "lcsc": fp_field(fp, "LCSC"),
            "dnp": fp_field(fp, "DNP") == "1" or ref.startswith(NO_ASSEMBLY_PREFIX),
            "x": pcbnew.ToMM(fp.GetPosition().x),
            "y": pcbnew.ToMM(fp.GetPosition().y),
            "rot": fp.GetOrientationDegrees() + jlc_rotation_offset(fp),
            "side": "top" if fp.GetLayer() == pcbnew.F_Cu else "bottom",
        })
    return out


def ref_key(ref):
    import re
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def bom_cpl(board):
    ps = sorted(parts(board), key=lambda p: ref_key(p["ref"]))
    assembled = [p for p in ps if not p["dnp"]]

    groups = OrderedDict()
    for p in assembled:
        groups.setdefault((p["value"], p["footprint"], p["lcsc"]), []).append(p["ref"])
    bom = os.path.join(FAB, "macs_esp32c6_bom.csv")
    with open(bom, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Quantity"])
        for (val, fpn, lcsc), refs in groups.items():
            w.writerow([val, ",".join(refs), fpn, lcsc, len(refs)])

    # CPL relativ zum Hilfsursprung (unten links), wie Gerber/Bohrdaten; y nach oben
    org = board.GetDesignSettings().GetAuxOrigin()
    x0 = pcbnew.ToMM(org.x)
    y1 = pcbnew.ToMM(org.y)
    cpl = os.path.join(FAB, "macs_esp32c6_cpl.csv")
    with open(cpl, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in assembled:
            w.writerow([p["ref"], f"{p['x'] - x0:.3f}mm", f"{y1 - p['y']:.3f}mm",
                        p["side"].capitalize(), f"{p['rot'] % 360:.0f}"])

    hand = [p for p in ps if p["dnp"] and not p["ref"].startswith(NO_ASSEMBLY_PREFIX)]
    return bom, cpl, assembled, hand


def pdfs():
    run(["kicad-cli", "pcb", "export", "pdf", "-o",
         os.path.join(FAB, "macs_esp32c6_pcb_top.pdf"),
         "--layers", "F.Cu,F.SilkS,F.Mask,Edge.Cuts", PCB])
    run(["kicad-cli", "pcb", "export", "pdf", "-o",
         os.path.join(FAB, "macs_esp32c6_pcb_bottom.pdf"), "--mirror",
         "--layers", "B.Cu,B.SilkS,Edge.Cuts", PCB])
    if os.path.exists(SCH):
        run(["kicad-cli", "sch", "export", "pdf", "-o",
             os.path.join(FAB, "macs_esp32c6_schematic.pdf"), SCH])


def main():
    os.makedirs(FAB, exist_ok=True)
    board = pcbnew.LoadBoard(PCB)
    z = gerbers()
    bom, cpl, assembled, hand = bom_cpl(board)
    pdfs()
    print("Gerber:", z)
    print("BOM:   ", bom, f"({len(assembled)} bestückte Bauteile)")
    print("CPL:   ", cpl)
    print("Nicht bestückt (Kupfer/optional):", ", ".join(p["ref"] for p in hand) or "-")


if __name__ == "__main__":
    main()
