# MACS bus findings (Electrolux / AEG tumble dryer)

The authoritative, machine-readable findings live in `src/device_bus_analyzer/spec/macs.yaml` (also shown in the
frontend under "Findings"). Every command, field, device and the run rules carry a status, exactly as for the BSH D-Bus:

* **confirmed** – verified (frame structure by arithmetic; values against what was done on the appliance)
* **assumed** – plausible and consistent with the recording, not yet verified by a targeted test
* **unknown** – seen on the bus, meaning not understood

Everything below comes from **one** AEG heat-pump dryer and **one** recording (idle heartbeat, every programme and option
stepped through, start, stop, switch-off). Anything that rests on a single recording is "assumed" at best.
The expansion of the abbreviation "MACS" could not be verified and is not used here.

## Physical layer (confirmed)
RAST 2.5 connector, 4 pins: 1 = +12 V, 2 = +5 V, 3 = DATA, 4 = GND. 9600 baud, 8 data bits, even parity, 1 stop bit,
**inverted** logic (idle = 0 V). The ESP32 board is powered from the bus and is therefore only online while the dryer is
on; the dryer switches itself off a few minutes after the last use. The collector copes with that (reconnect with back-off).
The bus supply is NOT permanent: measured on a neighbouring connector of the same bus, +12 V appears when the mains plug is
inserted and again drops after 10 to 15 s, and the same happens after switching the dryer off (+12 V for 10 to 15 s, then dead;
measured once, with a multimeter). A board powered only from the bus is online for a few seconds after power-up at best, so
it needs fast WLAN reconnect (`fast_connect`, optionally a static address) or it misses the first telegrams.

## Pause and resume (second recording)
Start, pause 4 s later, 3 h of silence, resume, off. During the pause the bus stays powered and carries only the heartbeat
(about 3760 frames in 3.1 h, no CRC errors, device state stays `04` paused). Pause is `22/2a51` byte 1 = `62`, resume is
`22/2a51` = `60`, byte-identical to the start message, so a remote start would send the same frame. Not yet tried on the
bus; nothing in this project transmits. The run detection treats a start while the controller reports paused as a
continuation of the same run (`resume_after_state` in the spec, assumed).

The programme selection (`22/2a50`) is sent when the dryer is switched on and when the programme button is pressed. A board
that is still booting at power-up misses it, so the run then has no programme name.

## Frame (confirmed: 246 of 249 frames in the recording have a valid checksum)

```
C9 DD SS LL <payload, LL bytes> XX          DD destination, SS source, XX = XOR of all preceding bytes
98 XX XX2                                   ACK: checksum byte of the message, then the XOR of both ACK bytes
```

* The **source is on the wire** (unlike the BSH D-Bus), so sender and receiver are not derived. What a device *is* is derived
  from its traffic and carries a status (`devices:` in the spec).
* The first payload byte is the message type. In the analyzer a command key reads `DD/SSTT`, for example `2a/225f` =
  heartbeat (type `5f`) from `22` to `2a`. The stored `cmd` is `source << 8 | type`, the stored data excludes the type byte;
  field byte numbers in the spec count from there.
* 3 of 249 frames failed the checksum. They sit in dense compressor traffic where frames are glued together; the parser
  resynchronises byte by byte and reports them instead of hiding them.

## Devices (assumed)
| Address | Role | Evidence |
|---|---|---|
| `0x22` | dryer control board (main controller) | sends heartbeat, state and time; wakes and polls `0x30` |
| `0x2A` | user panel | sends programme, start/stop, on/off; acknowledges the heartbeat |
| `0x30` | compressor / inverter board | answers status queries from power-on, also while idle; identifies as ASCII `M1IB1606` |
| `0x00` | broadcast | target of the compressor board's wake-up |

## Messages seen
| Key | Meaning | Status |
|---|---|---|
| `2a/225f` | heartbeat `5f 03`, every 3 s, always acknowledged | confirmed |
| `22/2a50` | programme selection; byte 13 = programme number 1…10 | confirmed (names not mapped) |
| `22/2a51` | panel command: `60` start, `61` programme selected, `62` stop/pause | assumed |
| `2a/2252` | device state: `0b` off, `03` starting after power-on, `01` ready, `02` running, `04` paused | assumed |
| `22/2a53` | on/off from the panel (one message, followed by state `0b`) | assumed |
| `22/3011` | compressor board identification `M1IB1606` | confirmed |
| `30/2210`, `00/3010`, `30/2214`, `22/3014` | wake-up and query handshake with the compressor board | assumed / unknown |
| `2a/2256` | time: falls by 1 per minute during a run, probably remaining minutes (not yet compared with the display) | unknown |
| `22/2a11` | panel identification (ASCII `U1CB820GZ`), sent once at power-on | assumed |
| `22/2a55`, `2a/2255` | programme data / option bits | unknown |
| `30/2211`, `30/2212`, `22/3012` | compressor parameters, inverter command and status | unknown |

## Runs
A run starts at the start command (`22/2a51` with byte 1 = `60`) and ends at the last telegram before a 10-minute silence;
both are marked *assumed*. No end-of-programme marker and no remaining-time message has been identified yet.

## Open points (need labelled recordings)
* meaning of the time messages (`2a/2256`), remaining time during a run
* option bits in `22/2a50` / `22/2a55` (only one option toggle was recorded), programme names
* end-of-programme and alarm messages (`2a/2257` was not seen)
* compressor values in the inverter status (`22/3012`)
* a second `51 00 60` appeared after the stop followed by an off sequence: resume or part of switching off is unclear

## Recording
Use `src/device_bus_analyzer/firmware/macs-analysis.example.yaml` with `src/device_bus_analyzer/firmware/macs_recorder.h`. The recorder assembles frames by their length
byte and writes one `RAW1` burst per frame (with its ACK) instead of cutting at a time gap, because the pauses inside a
frame are not reliably shorter than the pauses between frames. Bytes that fit no frame are kept raw as their own burst.

## Programme numbers (assumed)

Byte 13 of `22/2a50` follows the programme knob. The names come from the order in which the user stepped through the
programmes on one dryer (display names, translated); no second recording has confirmed them yet.

| Value | Programme | Value | Programme |
|---|---|---|---|
| 1 | Mix Dry | 6 | Bedding XL |
| 2 | Eco | 7 | Sportswear |
| 3 | Cotton | 8 | Down |
| 4 | Easy care | 9 | Light ironing |
| 5 | Delicates | 10 | Refresh |

Option encoding in `22/2a50` (assumed, one recording, values compared with the user's display readings):

- byte 7: drying time in minutes, 10 to 120 in 10-minute steps (then back to 0)
- byte 8 bit 7: delayed start set (`4b` without, `cb` with)
- bytes 9-10: delayed start in minutes (big endian): 30-minute steps up to 2 h, then hourly up to 20 h (1200), then back to 0

Drying degree, signal and anti-crease (Knitterschutz) bits are not decoded yet.
