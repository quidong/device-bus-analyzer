# Hardware

`macs-esp32c6/` – ESP32-C6 board that listens on the MACS bus of Electrolux/AEG appliances (and can be adapted for
other 9600 baud 8E1 inverted buses). It is powered from the bus, so it is online only while the appliance bus is
powered. Contents: SKiDL schematic source (`circuit.py`), KiCad project, Gerber/BOM/CPL for JLCPCB (`fab/`), 3D-printable
enclosure (`enclosure/`), ESPHome firmware for stand-alone sniffing (`firmware/`) and tests. The firmware that feeds the
analyzer is in `src/device_bus_analyzer/firmware/`.

Status: version 1.2, ordered from JLCPCB; the board has been measured on one AEG heat-pump dryer only.
The hardware licence is not decided yet; until then the repository licence does not automatically cover these files.

Tests: `cd hardware/macs-esp32c6 && python -m pytest tests` (needs `skidl`, `trimesh`, `numpy`, `pyyaml`).
