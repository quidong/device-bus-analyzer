# device-bus-analyzer

Collect, store, decode and inspect the internal bus telegrams of household appliances without ever transmitting on the bus.
Protocols: **BSH D-Bus** (Bosch / Siemens / Neff dishwashers) and the **Electrolux/AEG MACS bus** (heat-pump dryers; findings with confirmed/assumed/unknown status, see `docs/protocols/macs.md`; run detection names the run by the programme chosen before the start).

```
ESP32 board on the appliance bus ──ESPHome native API──▶ collector ─▶ SQLite (raw bursts, append-only)
                                                                         │
                                          decoder library + protocol spec (confirmed / assumed / unknown)
                                                                         │
                                    read-only HTTP API ─▶ web frontend (login) ─▶ MCP server (Claude Desktop)
```

* **Passive by design.** The collector only connects and subscribes to the device log; there is no code path that
  sends anything to a device or to the bus. The HTTP API is GET-only (a test asserts this). The web UI manages the local
  device list (add, edit, pause, delete with all its data) and never writes to an appliance.
* **Raw first.** Every burst is stored unchanged; decoded frames can be rebuilt at any time (`dba rebuild`), so better
  decoders never require re-recording.
* **Findings are data.** `src/device_bus_analyzer/spec/<protocol>.yaml` drives both the decoder and the findings page. Each
  command and field carries a status (`confirmed`, `assumed`, `unknown`) and its evidence.
* **No private data in the repository.** Logs stay on your server. `dba sanitize` strips SSID, MAC, IP, hostnames and keys
  before you share a log; a test scans the repository for such leftovers.

## Quick start (Portainer / Docker)

1. Flash an ESPHome board with firmware that emits Logformat 1 (`docs/LOGFORMAT.md`). The matching ESPHome YAML for each device is shown in the app under **Devices > Firmware** (copy or download); the files live in `src/device_bus_analyzer/firmware/`: `bshdbus-analysis.example.yaml` for the dishwasher, `macs-analysis.example.yaml` + `macs_recorder.h` for the dryer.
   Enable the API encryption key in ESPHome.
2. In Portainer create a stack (Web editor: paste `docker-compose.yml`; the image `ghcr.io/quidong/device-bus-analyzer:latest` is built by GitHub Actions on every push to `main`) and set these **stack variables** (nothing secret is stored in the repo). Devices are *not* stack variables any more, add them in the UI (step 3):

| Variable | Meaning |
|---|---|
| `DBA_DEVICES` | *optional, one-time import*: `name@host[:port]/protocol`, comma separated, for example `geschirrspueler@192.0.2.10:6053/bshdbus` |
| `DBA_KEY_<NAME>` | *optional, one-time import*: ESPHome API encryption key of that device (`DBA_KEY_GESCHIRRSPUELER`) |
| `ADMIN_EMAIL` | the single admin account (login = e-mail address) |
| `ADMIN_PASSWORD_HASH` | argon2id hash, create with `echo -n 'your password' \| docker run -i --rm ghcr.io/quidong/device-bus-analyzer:latest dba hash-password` |
| `ADMIN_PASSWORD` | alternative to the hash (plain text in the stack; the hash is preferred) |
| `SESSION_SECRET` | 32+ random characters, signs the session cookie |
| `API_TOKEN` | token for the MCP extension and scripts (optional) |
| `DBA_TZ` | display timezone, default `Europe/Berlin` |

3. Open `http://<host>:8080` (optional HTTPS: set `DBA_TLS=1` and `DBA_TLS_HOSTS`, then install the local CA once from `/tls/ca.crt`), sign in, then **Devices > New device**: choose type, manufacturer and model (suggestions from
   `src/device_bus_analyzer/catalog.yaml`, free text is allowed; the manufacturer selects the decoder protocol), enter host, port and the
   ESPHome API key. Collection starts immediately and changes apply without a restart. Expose it in your LAN only; there is no password reset and no e-mail sending.
   If you must put it behind a reverse proxy, set `COOKIE_SECURE=1` and terminate TLS there.

**Device management.** Devices live in the SQLite database in the data volume (table `devices`, host and key included, so back up the
volume like a secret). The key is write-only: the UI shows only whether one is set. *Edit* changes type/model/connection, *Pause* stops collecting and keeps all data,
and *Delete* removes the device with all its frames, bursts, heartbeats, sessions and logs after you type its name (irreversible).
After saving a new device the **Firmware** page shows the recommended ESPHome YAML (and header) for its protocol with copy/download buttons. A device's name and protocol are fixed once
created, because the name identifies the data and the decoder depends on the protocol. **Upgrading an existing installation:**
leave `DBA_DEVICES` / `DBA_KEY_*` in the stack for the first start; they are imported once into the database without overwriting
anything configured in the UI. Afterwards open **Devices**, assign type/manufacturer/model, and remove the variables if you like.
Type, manufacturer and model are only recorded for now (they will let findings be split into "general for the protocol" and "specific
to a model"); decoding is unchanged. New catalogue entries are welcome as pull requests to `catalog.yaml`.

Devices that are only online sometimes (a dryer that connects when switched on) are fine: the collector reconnects forever
with back-off and the data model records board restarts and gaps explicitly.

## Companion: learn the buttons and menus of your appliance
Open **Companion** on a device (made for the phone, while you stand at the appliance). Switch the appliance on first. Then either run a **guided check** (tap *Go* once: a 90 s hands-off phase measures the appliance's own noise in exactly that state, then every step shows its instruction, waits where the appliance only reports every few seconds, and ends with *Done*) (open and close the door three times, step through the programs, switch an option on and
off; each step is timed, so your reaction time does not matter; the analysis judges noise per bit, so a flapping bit next to the door bit does not hide it) or **mark actions freely** (door opened, program
selected, start pressed, display shows ..., or your own text, optionally with the menu level you are in). Every action is timed on the
server and shown between the telegrams in the timeline.

**Learned** compares the bytes before and after each action. A byte only counts when it changes again for the same action and does
not change on its own (a noise model is measured on the quiet time of the recording). Repeats give *assumed*; if the opposite action
(door closed) flips the same byte back, the finding is *confirmed*. You accept findings with a meaning of your own; **Export
findings** writes only those (addresses, byte positions, values, device model) as JSON for a pull request or issue. Telegrams, times,
host names and keys are never part of it. The companion sends nothing to the appliance. Actions and accepted findings are deleted
together with the device.

### Display values, Home Assistant, sharing
The guided check **Read the display** (enter the shown time or number five times while it changes) lets **Learned** find the bytes
that carry it (minutes, hours and minutes, or a number; 8 or 16 bit, factor 1 or 0.1). Accepted findings and values are shown next to
the telegrams in the timeline and frames, and as **Now** on the device card.

**Home Assistant** (device card or Learned page): the page shows the current values and a ready `rest:` configuration that reads
`/api/{device}/state` with your API token. Decoding happens on the server; the ESPHome firmware only streams raw telegrams.

**Share** with *Export findings* (JSON) or *Spec suggestion* (YAML for the protocol spec, always status *assumed*). Put the JSON
under `contributions/<protocol>/`; CI checks the file (`dba validate-contribution`, no telegrams, times, addresses or keys allowed).
`dba suggest-spec FILE` prints the YAML for a contribution.

**Backup** (header): download a consistent snapshot of the database, or restore one (type RESTORE; the file contains the ESPHome
keys, keep it private). **Help** explains how to record a good run. The MCP extension also offers `list_markers`, `learn_analysis`
and `device_state`.

The web interface is available in German, English, Spanish, French and Italian (switcher in the header; the browser language is detected, the choice is remembered).

### Device knowledge updates (no new image needed)
Protocol specs, the device catalogue and the recommended firmware live in the repository and can be refreshed in a running container:
**Device knowledge** (link on the start page) checks once a day (switchable) or on demand, and the MCP tool `update_knowledge` does the
same. Only data files listed in `knowledge-manifest.json` are fetched from GitHub, verified by SHA-256, validated with the normal spec and
catalogue checks and only then activated; a failed update changes nothing, *Reset* returns to the shipped files. Recorded data is never
touched and decoding uses the new knowledge at once. Checks are rate limited to one per minute. After changing a spec, the catalogue or a
firmware file run `dba build-knowledge` (a test fails otherwise). `DBA_KNOWLEDGE_URL` overrides the manifest address. The container needs
outbound HTTPS to raw.githubusercontent.com. The MCP tool `get_firmware` returns the firmware files of a device.

Security notes and what is protected how: see [SECURITY.md](SECURITY.md).

## Command line

```
dba import --source <name> --protocol bshdbus log1.txt log2.txt   # import saved ESPHome logs (date from file name or --date)
dba rebuild                                                       # re-decode frames from stored raw bursts
dba validate-spec bshdbus                                         # consistency check of the protocol spec
dba gaps log.txt                                                  # find lost bursts in a log
dba sanitize log.txt > clean.txt                                  # remove private details before sharing
dba collect | dba serve [--no-collector]
```

## MCP for Claude Desktop (extension)

The connection is meant for local operation and works with Claude only (Claude Desktop, Claude Code); the **AI connection** page in the app has the download, address and token. `extension/` is a Claude Desktop extension (`.mcpb`, Node). Build it with `cd extension && npm ci --omit=dev && npx @anthropic-ai/mcpb pack`
(the `extension` workflow also builds it on every change) and open the file in Claude Desktop. The install dialog asks for the
**analyzer URL** (for example `http://192.0.2.10:8089`, or `https://…` with `DBA_TLS=1` and the CA file from the HTTPS page) and the **API token** (`API_TOKEN` of the stack, stored as a sensitive value).
Nine tools (read access only): `list_sources`, `get_findings`, `list_runs`, `command_overview`, `command_values`, `timeline`, `frames`,
`raw_bursts`, `data_quality`. Every one is a GET against the API.

## Sender, ACK node and runs
A BSH D-Bus frame carries only its **destination**. Sender, receiver and the node that acknowledged (high nibble of the ACK
byte) are therefore *derived* from the spec (`nodes`, `acks`) and always shown with a status (`confirmed` / `assumed` /
`unknown`; unknown means the value is `null`). Per-field decode values carry their own status as well.

Telegrams are grouped into **runs** (program cycles): a run starts at the start command and ends at the last telegram before a
silent gap (rules in `spec/<protocol>.yaml`, `runs:`). Open a run in the frontend under "Runs", or pass its id as `run` to the API
(`/api/<source>/frames?run=<id>`, also `timeline` and `bursts`) and to the MCP tools.

## Development

```
pip install -e ".[dev]"
(cd extension && npm ci)   # optional: enables the extension test
pytest -q
```
Tests use synthetic telegrams only. Add real-device evidence to the spec as `evidence` text, never as log files.

## Contributing findings
Attach the JSON from **Export findings** to an issue, or open a pull request that changes `spec/<protocol>.yaml` (status + evidence) and, if useful, adds a synthetic test.
Please do not commit logs, MAC/IP addresses, SSIDs or serial numbers.

## Licenses
Code: MIT (`LICENSE`). Protocol documentation and spec files: CC BY 4.0 (`LICENSE-DOCS.md`).
