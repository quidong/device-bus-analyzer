#!/usr/bin/env bash
# Kompletter Durchlauf: Schaltung -> Schaltplan -> Platine (geroutet) ->
# Fertigungsdaten -> Tests.
# Voraussetzungen: KiCad 7+ (kicad-cli, pcbnew-Python), Java 21,
#   pip: skidl schematizer kinet2pcb pytest pyyaml
#   Freerouting-JAR unter /opt/freerouting/freerouting-2.1.0.jar
set -euo pipefail
cd "$(dirname "$0")"
export KICAD7_SYMBOL_DIR=${KICAD7_SYMBOL_DIR:-/usr/share/kicad/symbols}

python3 tools/make_esp_symbol.py lib/macs.kicad_sym
python3 tools/make_rast_footprint.py
python3 circuit.py build/macs_esp32c6.net --schematic
python3 build_pcb.py

python3 make_fab.py
python3 enclosure/make_enclosure.py
python3 -m pytest -q tests/
