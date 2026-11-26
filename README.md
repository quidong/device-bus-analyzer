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

Hardware: the MACS board (schematic, KiCad, Gerber, enclosure) is in [`hardware/`](hardware/README.md).

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
| `SESSION_SECRET` | optional: created on the first start and kept in the data volume; a value set here wins and is adopted (32+ random characters) |
| `API_TOKEN` | optional: created on the first start (shown on the *AI connection* page); a value set here wins and is adopted |
| `DBA_TZ` | display timezone, default `Europe/Berlin` |

3. Open `http://<host>:8080` (optional HTTPS: set `DBA_TLS=1` and `DBA_TLS_HOSTS`, then install the local CA once from `/tls/ca.crt`), sign in, then **Devices > New device**: choose type (dishwasher, washing machine, tumble dryer or your own), manufacturer, bus system and model (type, manufacturer and model
   are required). Every manufacturer and every bus is offered for every type; the manufacturer presets its usual bus, which you can
   change. Known models come from `src/device_bus_analyzer/catalog.yaml`; a model or manufacturer you type in is remembered and
   suggested again, even after its device is deleted. Then enter host, port and the
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

## Analysis with Claude (MCP)
The app records and decodes what the spec already knows; the analysis of the unknown parts is done by **Claude** through the AI
connection (MCP). Record **complete runs** (choose a program, start it, let it finish) and note down what you did at the appliance and
when ("20:14 door opened"). Repeat interesting actions a few times. Then connect Claude (account menu → *AI connection*) and use one
of the example prompts on that page (overview, analyse a run with your actions, find display values, explain unknown commands,
write a contribution file, export a complete run). The device card shows how much of a recording is already **analysed**: the share
of telegram types (destination + command) that the spec describes (confirmed or assumed) or for which a finding was accepted. It
counts types, not telegrams, so a heartbeat sent every minute weighs no more than a command that appears twice.

There are two ways to give knowledge back to the project: **complete runs** (let Claude export a run with times relative to its
start and without host names, addresses or keys, and attach it to an issue) or **analysed findings** (let Claude write a contribution
file for `contributions/`; see *Contributing findings*).

The former companion (guided checks and manual marking) has been removed. Actions and findings recorded with it stay in the
database: devices that have them still show the **Learned** page (accept findings, export, spec suggestion), and the MCP tools
`list_markers` and `learn_analysis` still return them.

### Display values, Home Assistant, sharing
Accepted findings and values are shown next to the telegrams in the timeline and frames, and as **Now** on the device card.

**Home Assistant** (device card or Learned page): the page shows the current values and a ready `rest:` configuration that reads
`/api/{device}/state` with your API token. Decoding happens on the server; the ESPHome firmware only streams raw telegrams.

**Share** a contribution file written by Claude, or from the Learned page *Export findings* (JSON) or *Spec suggestion* (YAML for the protocol spec, always status *assumed*). Put the JSON
under `contributions/<protocol>/`; CI checks the file (`dba validate-contribution`, no telegrams, times, addresses or keys allowed).
`dba suggest-spec FILE` prints the YAML for a contribution.

**Backup** (header): download a consistent snapshot of the database, or restore one (type RESTORE; the file contains the ESPHome
keys, keep it private). **Help** explains the way from recording to finding. The MCP extension also offers `list_markers`, `learn_analysis`
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
Attach a contribution file written by Claude (or the JSON from **Export findings** on the Learned page) or an exported complete run to an issue, or open a pull request that changes `spec/<protocol>.yaml` (status + evidence) and, if useful, adds a synthetic test.
Please do not commit logs, MAC/IP addresses, SSIDs or serial numbers.

## Licenses
Code: MIT (`LICENSE`). Protocol documentation and spec files: CC BY 4.0 (`LICENSE-DOCS.md`).

## Design principles of the UI

- **Everything that can change is live.** Regions marked `data-live="…"` are refreshed from the server every few seconds (paused while the tab is hidden or a field in the region has focus); a changed list of devices reloads the page. New pages must mark their changing parts the same way (`static/ui.js`).
- **Settings page** (account menu → Settings): time zone, sign-in duration, knowledge update address, HTTPS (restart needed), renew the API token, change the password. Values saved there win over the stack variables, which only provide the defaults.
- **One account menu** (avatar, top right) holds language (a select), help, AI connection, knowledge, HTTPS, backup and logout.
- **Device cards:** icon and name open the device (its runs); all actions are uniform icon buttons with a tooltip (telegrams, Home Assistant, firmware, pause/resume, edit = pencil, delete = bin); the card shows the analysed share instead of the telegram count.
