# MACS bus findings (Electrolux / AEG tumble dryer)

The authoritative, machine-readable findings live in `src/device_bus_analyzer/spec/macs.yaml` (also shown in the
frontend under "Findings"). Every command, field, device and the run rules carry a status, exactly as for the BSH D-Bus:

* **confirmed** – verified (frame structure by arithmetic; values against what was done on the appliance)
* **assumed** – plausible and consistent with the recording, not yet verified by a targeted test
* **unknown** – seen on the bus, meaning not understood

Everything below comes from **one** AEG heat-pump dryer: a first recording (idle heartbeat, every programme and option
stepped through, start, stop, switch-off), a pause/resume recording, one complete wet run from start to self power-off,
and one short run with laundry that was already dry. Anything that rests on a single recording is "assumed" at best.
The expansion of the abbreviation "MACS" could not be verified and is not used here.

## Physical layer (confirmed)
RAST 2.5 connector, 4 pins: 1 = +12 V, 2 = +5 V, 3 = DATA, 4 = GND. 9600 baud, 8 data bits, even parity, 1 stop bit,
**inverted** logic (idle = 0 V). The ESP32 board is powered from the bus and is therefore only online while the dryer is
on; the dryer switches itself off a few minutes after the last use. The collector copes with that (reconnect with back-off).
The bus supply is NOT permanent: measured on a neighbouring connector of the same bus, +12 V appears when the mains plug is
inserted and again drops after 10 to 15 s, and the same happens after switching the dryer off (+12 V for 10 to 15 s, then dead;
measured once, with a multimeter). A board powered only from the bus boots when the dryer is switched on; until the
collector has connected and subscribed to the log, ESPHome drops log lines. Without a buffer the first telegrams were lost
(in one session the first 18 bursts, about 18 s). The recorder therefore buffers RAW1/HB1 lines in RAM (`use_buffer(400)`,
about 5 min of traffic) until a client subscribes to the log at INFO level, then replays them in order with their original
`seq` and `t_us`; it buffers again if the connection drops. The store gives such frames their board time once the first
heartbeat with a clock time arrives. Fast WLAN reconnect (`fast_connect`, optionally a static address) still helps.

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
| `0x30` | motor inverter board (drum motor) | answers status queries from power-on, also while idle; identifies as ASCII `M1IB1606`; takes a signed drum speed set point and reports the actual speed (whether it also drives the compressor is unknown) |
| `0x00` | broadcast | target of the wake-up messages at power-on and start |

## Messages seen
| Key | Meaning | Status |
|---|---|---|
| `2a/225f` | heartbeat `5f 03`, every 3 s, always acknowledged | confirmed |
| `22/2a50` | programme selection; byte 13 = programme number 1…10 | confirmed (names not mapped) |
| `22/2a51` | panel command: `60` start, `61` programme selected, `62` stop/pause | assumed |
| `2a/2252` | device state (byte 1): `0b` off, `03` idle after power-on or after the programme ended, `01` ready, `02` running, `04` paused, `09` cancelled; byte 2 = phase (`01` drying, `02` cooling, `04` anti-crease); byte 8 = how it ended (`70` normally, `40` early, laundry already dry) | assumed |
| `22/2a53` | on/off from the panel: `10` off (button and self power-off), `20` off after a cancel, `00` once at power-on | assumed |
| `22/3011` | motor inverter board identification `M1IB1606` | confirmed |
| `30/2210`, `00/3010`, `30/2214`, `22/3014` | wake-up and query handshake with the motor inverter board | assumed / unknown |
| `2a/2256` | time, byte 1 = layout. Layout `00`: **byte 3 = remaining time in minutes as on the display**; layout `05`: anti-crease countdown; `02` while ready; `03` at the end; `04` programme default? | confirmed (remaining time) / assumed |
| `2a/2257` | alarm? only `03 00 00 00 00` once per power-on (no alarm) | unknown |
| `22/2a11` | panel identification (ASCII `U1CB820GZ`), sent once at power-on | assumed |
| `22/2a55`, `2a/2255` | programme data / option bits | unknown |
| `30/2211` | parameter blocks for the motor inverter board, sent at every start | unknown |
| `30/2212` | drum command: bytes 1-2 signed speed set point (`+1840`, `+2760`, `-2760` reversal, `+-1932` anti-crease, `0` stop) | assumed |
| `22/3012` | drum status: actual speed (bytes 1-2, bit 15 = set point reached), temperature in deg C (byte 7), motor current (bytes 8-9), **laundry moisture** (bytes 14-15 and 16-17) | assumed |
| `2a/2210`, `2a/2211`, `2a/2253`, `00/2210`, `00/2a10` | power-on sequence (wake-ups, controller identification, on/off echo) | unknown / assumed |

## A complete run (one wet run, Eco)
| Phase | What the bus shows |
|---|---|
| start | `22/2a51 = 60`, state `02`, phase `01`; wake-up and parameter blocks for `0x30`; drum starts at +1840 and, with wet laundry, goes to +2760 after the first reversal (with dry laundry it stayed at 1840) |
| drying (about 3.9 h) | remaining time in `2a/2256` layout `00`, re-estimated several times; a short reversal (stop, -2760, stop, +2760) every 40 min; moisture fell from about 320 to 120 |
| cooling (about 40 min) | phase `02`, byte 5 = `05`; the temperature falls |
| anti-crease (about 30 min) | phase `04` when the remaining time reaches 0; drum +-1932 for 5 s every 33 s, layout `05` counts down from 29 |
| end | state `03`, byte 8 = `70`; drum idle command; moisture and current go to 0 |
| self power-off (5 min later) | `22/2a53 = 10`, state `0b`, the bus goes dead |

With laundry that was already dry the moisture read 62-66 from the first minute and the programme ended after 5 min with
state `03`, byte 8 = `40` (no cooling, no anti-crease), followed by the same self power-off.

## Runs
A run starts at the start command (`22/2a51` with byte 1 = `60`) and ends at the first device state `03`, `09` or `0b`
after it, or at the last telegram before a 10-minute silence (the board is powered from the bus). The remaining time at
the start and end comes from `2a/2256` layout `00`. When the start command was missed because the board was still booting
(about 18 s after power-on), the first drum command with a speed set point outside every detected run starts the run
(`fallback_start`, `start_by = fallback`). All of this is *assumed*.

## Open points (need labelled recordings)
* option bits in `22/2a50` / `22/2a55` (only one option toggle was recorded), programme names
* alarm messages (`2a/2257` only ever carried zeros)
* byte 5 of `2a/2256` layout `00` (a second minute counter), layouts `02`, `03`, `04`
* units of motor current and moisture, whether `0x30` also drives the compressor
* door open/closed (`2a/2252` byte 6 toggled 41/43, not yet tested with a single labelled action)

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
