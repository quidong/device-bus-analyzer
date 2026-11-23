# MACS-ESP32-C6 – universeller Adapter für Electrolux/AEG/Zanussi

ESPHome-Platine für den internen **MACS-Bus** von Electrolux-Geräten
(Waschmaschine, Trockner, Backofen, Kochfeld). Ein ESP32-C6 liest den Bus mit
und kann auch senden. Version 1.1 orientiert sich im Aufbau am
[BSH-Board von Bouni](https://github.com/Bouni/BSH-Board) (gleicher Zweck,
anderes Protokoll).

Grundlage: Reverse Engineering von
[agocsdaniel/esphome_electrolux_macs](https://github.com/agocsdaniel/esphome_electrolux_macs)
(Pinout, Pegel, Framing) und das Electrolux-Servicehandbuch *SidekickPC*.

---

## ⚠️ Sicherheit zuerst

* Die Elektronik in diesen Geräten ist **oft nicht vom Netz getrennt**. GND des
  MACS-Busses kann Netzpotenzial führen. Messungen nur mit isolierten
  Messgeräten, Gerät beim Anschließen vom Netz trennen (Stecker ziehen).
* **USB-C niemals benutzen, während die Platine am Gerät hängt.** USB ist nur
  zum ersten Flashen auf dem Tisch gedacht; danach Updates per WLAN (OTA).
* Der Sender ist fest mit dem Bus verbunden. Ein Basis-Pulldown hält ihn beim
  Booten aus; solange die Firmware nichts sendet, ist er hochohmig.

---

## Technische Daten

| | |
|---|---|
| Größe | 30 × 54 mm, 2 Lagen, 1,6 mm (Antenne ragt oben 6 mm über) |
| MCU | ESP32-C6-WROOM-1-N8 (WLAN 6, Thread/Zigbee, BLE) – WROOM statt MINI, weil JLCPCB das MINI nur in der teuren Standard-Bestückung verarbeitet |
| Versorgung | +12 V vom Bus (Standard) oder +5 V vom Bus (JP2), USB-C zum Flashen |
| Regler | AP63203 Step-Down, 3,8–32 V Eingang, feste 3,3 V |
| Schutz | TVS SMF15A auf +12 V, Z-Dioden 5,6 V auf DATA und +5 V, ESD-Schutz USB |
| MACS-Anschluss | RAST-2.5-Steckkante 4-polig direkt auf der Platine (1 = +12 V, 2 = +5 V, 3 = DATA, 4 = GND), Kontakte beidseitig, Codierschlitz zwischen 3 und 4 |
| Bus RX | Teiler 4k7/10k + 1 nF → GPIO18, 5 V → 3,4 V, Last < 0,4 mA |
| Bus TX | NPN + P-MOSFET schaltet +5 V über 100 Ω auf DATA ← GPIO19 |
| LEDs | Power (rot, fest), Status (grün, GPIO8), Bus-Aktivität (blau, GPIO21) |
| Extras | 12-V-Erkennung (GPIO0, ADC), Testpunkte DATA/GND/5V/3V3 und IO2/IO3/IO22, Pads für BOOT/RESET-Taster (nicht bestückt, Flashen geht über USB) |

### Lötbrücke

| | Auslieferung | Bedeutung |
|---|---|---|
| **JP2** | 1–2 gebrückt | 1–2 = Versorgung aus +12 V, 2–3 = aus +5 V (Leiterbahn zwischen 1–2 durchtrennen, 2–3 verzinnen) |

### Busstufe – Annahme zur Polarität
Laut den Messungen im Referenzprojekt ist DATA **in Ruhe 0 V** und aktiv
**5 V** (invertierter UART). Die Senderstufe ist deshalb ein High-Side-Treiber
(zieht DATA auf 5 V, Ruhe hochohmig). Beim ersten Anschluss zuerst nur
mitlesen (`macs-sniffer.yaml`) und an TP1 (DATA) gegen TP2 (GND) prüfen:
in Ruhe ≈ 0 V mit kurzen Ausschlägen. Liegt dort dauerhaft ~5 V an, ist die
Logik bei deinem Gerät umgekehrt – dann nicht senden und melden.

---

## Bestellung bei JLCPCB

1. **Gerber hochladen:** `fab/macs_esp32c6_gerber.zip`
   – 2 Lagen, 1,6 mm, Standardwerte; Farbe nach Wunsch.
   Die Antenne des ESP-Moduls ragt absichtlich 6 mm über den Platinenrand
   (beste Funkleistung). Fragt JLC bei der Bestückung nach, das bestätigen.
2. **PCB Assembly** aktivieren, „Assemble top side“.
3. **BOM** `fab/macs_esp32c6_bom.csv` und **CPL** `fab/macs_esp32c6_cpl.csv`
   hochladen. Alle Bauteile haben LCSC-Nummern.
4. In der **Bauteil-Vorschau die Drehung prüfen** (v. a. Dioden, USB-C,
   SOT-23-Teile). Das ist bei JLC immer nötig – Abweichungen dort per
   Drehknopf korrigieren.
5. **PCBA Type „Economic“**, Oberfläche **LeadFree HASL** (die Steckerfedern
   sind verzinnt, Zinn auf Zinn kontaktiert gut; ENIG wäre ~15 $ teurer),
   Dicke **1,6 mm** (RAST-Norm 1,5 ± 0,14; 1,6 funktioniert beim BSH-Board).
   Die CPL enthält bereits die JLC-Drehkorrekturen (SOT-23 +180°,
   SOT-23-6/TSOT-23-6 +270°, in der JLC-Vorschau geprüft).
6. J2 (Steckkante), die Taster SW1/SW2 und die Testpunkte sind nicht bestückt
   und stehen deshalb nicht in BOM/CPL.

### Steckkante und Kabel
Vorbild ist die Steckkante des [BSH-Boards](https://github.com/Bouni/BSH-Board),
auf 4 Pole erweitert:

* Zunge mit 4 Kontaktflächen im 2,5-mm-Raster, **oben und unten** (über
  Durchkontaktierungen verbunden) – egal, auf welcher Seite die Federn des
  Steckers liegen. Keine Lötpaste auf den Kontakten.
* Aussparung 13,2 × 2,5 mm: Die Platinenwangen links und rechts führen den
  Stecker seitlich.
* Codierschlitz 1,0 mm (JLCPCB-Minimum) zwischen Kontakt 3 und 4 – passt zum
  Trockner. Stecker **mit** Codiersteg (Lumberg 3517 04 K01) gehen nur richtig
  herum drauf, Stecker **ohne** Codierung (Würth WR-RAST 667101210104) passen
  ebenfalls.

**Kabel:** an beiden Enden derselbe Schneidklemm-Stecker, Adern 1:1
(1→1 … 4→4). Leitung LiYY 4 × 0,25 mm² (passt für Lumberg 0,14–0,38 mm² und
Würth AWG 24–22).

* Stecker gleichmäßig eindrücken (Schraubstock, Adern sauber abgeschnitten),
  danach Durchgang messen und dabei am Kabel wackeln.
* **Ohne Codierung kann man den Stecker umgedreht aufstecken** (1↔4, 2↔3 –
  dann liegen 12 V auf GND). Kontakt 1 am Stecker und an beiden Platinen
  farbig markieren und vor dem Einschalten prüfen: zwischen Pad 1 und 4 an
  unserer Platine müssen bei eingestecktem Kabel +12 V anliegen.

---

## Inbetriebnahme

1. Platine **ohne Gerät** per USB-C an den PC. Der ESP32-C6 wird über seine
   eingebaute USB-Schnittstelle ohne Taster geflasht (ESPHome/esptool setzen
   ihn selbst in den Download-Modus).
2. `firmware/macs-sniffer.yaml` (nur mitlesen; für den Trockner empfiehlt sich die Firmware aus `src/device_bus_analyzer/firmware/macs-analysis.example.yaml`) oder
   `firmware/macs-washer.yaml` mit ESPHome flashen (`secrets.yaml` mit
   `wifi_ssid`/`wifi_password` anlegen; `__API_KEY__`/`__AP_PASSWORD__`
   ersetzt der Device Builder beim Anlegen). Danach USB abziehen.
   **Fabrikneues Modul ohne Firmware:** Der Chip startet ohne gültiges
   Programm ständig neu, Windows meldet das USB-Gerät dann alle paar
   Sekunden neu an. Kommt das Flashen nicht durch: die Pads von SW1 (BOOT)
   beim Einstecken mit einer Pinzette überbrücken – der Chip bleibt dann im
   Download-Modus.
3. Gerät stromlos machen, Platine anschließen, Gerät einschalten.
   Im ESPHome-Log erscheinen die Frames als Hex; „Bus 12V“ zeigt ~12 V.
4. Mitschnitt auswerten: `python3 tools/macs_frames.py < log.txt`
5. Waschmaschine mit EWX-Steuerung: `firmware/macs-washer.yaml` (Decoder von
   agocsdaniel). Trockner: dessen EDR-Beispiel übernehmen.

---

## Dateien

| Pfad | Inhalt |
|---|---|
| `circuit.py` | Schaltung als Code (SKiDL) – **Quelle der Wahrheit** |
| `build/macs_esp32c6.kicad_pro` | KiCad-Projekt (öffnet in KiCad 7, 8, 9): Schaltplan (hierarchisch, Netzlabel-Stil) + Leiterplatte, Regeln für JLCPCB hinterlegt |
| `fab/` | Gerber-ZIP, BOM, CPL, Schaltplan- und Layout-PDF |
| `firmware/` | ESPHome-Konfigurationen |
| `tools/macs_frames.py` | MACS-Frames aus Logs zerlegen, Prüfsumme prüfen |
| `tests/test_board.py` | Testsuite (Schaltung, Layout/DRC, Fertigungsdaten, Firmware) |
| `make_all.sh` | Kompletter Neuaufbau inkl. Autorouting (Freerouting) und Tests |
| `build_pcb.py --use-ses` | Platine mit dem gespeicherten, geprüften Routing neu erzeugen (ohne neues Autorouting) |

Der Schaltplan ist automatisch aus `circuit.py` erzeugt: Verbindungen laufen
über Netzlabels statt Drähte. Für Änderungen am besten `circuit.py` anpassen
und `make_all.sh` laufen lassen; kleine Layout-Korrekturen gehen direkt in
KiCad.

## Tests

```
python3 -m pytest -q tests/
```

Geprüft wird u. a.: Pinout der MACS-Stecker, GPIO-Zuordnung, sichere
Strapping-Pins, Pegel des RX-Teilers, Reglerausgang 3,30 V, ADC-Bereich,
jedes Pad auf der Platine gegen die Netzliste, DRC ohne Fehler und ohne offene
Verbindungen, BOM/CPL konsistent mit LCSC-Nummern, ESPHome-YAML passt zur
Platine, MACS-Prüfsumme und Log-Parser.

---

## Gehäuse (3D-Druck)

`enclosure/macs_gehaeuse_unterteil.stl` und `enclosure/macs_gehaeuse_deckel.stl`
(Deckel liegt schon in Druckausrichtung, Oberseite aufs Bett; er ist um die X-Achse gedreht, nicht gespiegelt – zum Montieren wieder um die X-Achse umdrehen, dann sitzt die USB-Aussparung an der USB-Seite).

* Platine ohne Befestigungslöcher: liegt auf einem umlaufenden Steg, der Deckel
  drückt sie mit Rippen fest. Deckel hält per Steckrand + Rastnasen.
* **Stecker:** Führungswände links/rechts vor der Zunge (0,3 mm Spiel, kein
  seitliches Verrutschen), zwei Niederhalter im Deckel über den Steckerenden
  (kein Abheben, Mitte frei für die Adern). Die Führungswände sind zugleich
  Anschlag für die Platine.
* **Kabel:** verlässt das Gehäuse stirnseitig durch eine geteilte Durchführung,
  die das Kabel (Ø 5 mm) leicht klemmt – das ist die Zugentlastung, der Stecker
  kann nicht abgezogen werden.
* **Abgedichtet:** keine Öffnungen für USB/Taster (USB nur zum ersten Flashen,
  Platine dafür herausnehmen); der Deckel greift mit einem 3 mm hohen Steckrand
  in das Unterteil (Labyrinth), die LEDs leuchten durch 1,2 mm Restwand.
  Für noch mehr Dichtheit vor dem Schließen eine dünne Silikonraupe auf die
  Oberkante des Unterteils.
* **Wandstärken für den FDM-Druck:** alle tragenden Wände 2,0 mm (Boden und
  Deckel 2,4 mm wegen der 0,4 mm tiefen Gravur), einzige Ausnahme sind die
  1,2-mm-Fenster über den LEDs (JLC3DP-Minimum). Geprüft mit
  `python3 enclosure/wall_thickness.py` und im Test.
* **Magnete wie beim BSH-Board:** 4 × Neodym 5 × 5 mm (z. B. supermagnete
  S-05-05-N) in Laschen außen an den Längsseiten. Die Bohrung geht durch,
  der Magnet sitzt bündig mit der Unterseite und liegt direkt am Blech. Mit
  einem Tropfen Sekundenkleber sichern, Polung bei allen gleich.
* **LEDs:** drei Lichtleiter im Deckel (PWR, ST, ACT) mit 1,2 mm Restwand –
  bei weißem ASA leuchten sie durch.
* Druck: ASA weiß (wärmefest bis ~98 °C, im Trockner wird es warm), 0,2 mm
  Schicht, ohne Stützmaterial. Bei JLC3DP: FDM, ASA, White.
* Steckermaße sind Annahmen (Breite 12,5, Höhe ≤ 4,8 mm über der Platine):
  Passt dein Stecker nicht, `plug_*` in `enclosure/make_enclosure.py` anpassen
  und `python3 enclosure/make_enclosure.py` laufen lassen.
