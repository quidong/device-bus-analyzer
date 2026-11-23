"""Konvertiert die von SKiDL/schematizer erzeugten .kicad_sch-Dateien in das
KiCad-7-Format (KiCad 8/9/10 öffnen KiCad-7-Dateien ebenfalls).

Aufruf: python3 sch_to_kicad7.py <eingabe_ordner> <ausgabe_ordner>
"""
import os
import re
import sys


def convert(text):
    text = re.sub(r"\(version \d+\)", "(version 20230121)", text, count=1)
    text = re.sub(r"\s*\(exclude_from_sim (yes|no)\)", "", text)
    text = re.sub(r'\s*\(generator_version "[^"]*"\)', "", text)
    text = re.sub(r"\s*\(embedded_fonts (yes|no)\)", "", text)
    text = text.replace("(fields_autoplaced yes)", "(fields_autoplaced)")
    text = text.replace("(hide yes)", "hide")
    text = re.sub(r"\s*\(hide no\)", "", text)
    # Hierarchie-Blätter: in_bom/on_board/dnp gibt es dort erst ab KiCad 8
    text = re.sub(r"(\(sheet\s+\(at [^)]*\)\s+\(size [^)]*\))"
                  r"\s*\(in_bom (?:yes|no)\)\s*\(on_board (?:yes|no)\)"
                  r"\s*\(dnp (?:yes|no)\)", r"\1", text)
    return text


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if f.endswith(".kicad_sch"):
            with open(os.path.join(src, f)) as fh:
                t = convert(fh.read())
            with open(os.path.join(dst, f), "w") as fh:
                fh.write(t)
            print("konvertiert:", f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
