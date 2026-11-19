# device-bus-analyzer

Collect, store, decode and inspect the internal bus telegrams of household appliances **read-only**.
Protocols: **BSH D-Bus** (Bosch / Siemens / Neff dishwashers) and the **Electrolux/AEG MACS bus** (heat-pump dryers; findings with confirmed/assumed/unknown status, see `docs/protocols/macs.md`; run detection names the run by the programme chosen before the start).

```
ESP32 board on the appliance bus ──ESPHome native API──▶ collector ─▶ SQLite (raw bursts, append-only)
                                                                         │
                                          decoder library + protocol spec (confirmed / assumed / unknown)
                                                                         │
                                    read-only HTTP API ─▶ web frontend (login) ─▶ MCP server (Claude Desktop)
```

* **Read-only by design.** The collector only connects and subscribes to the device log; there is no code path that
  sends anything to a device or to the bus. A test asserts that the API has no write routes.
* **Raw first.** Every burst is stored unchanged; decoded frames can be rebuilt at any time (`dba rebuild`), so better
  decoders never require re-recording.
* **Findings are data.** `src/device_bus_analyzer/spec/<protocol>.yaml` drives both the decoder and the findings page. Each
  command and field carries a status (`confirmed`, `assumed`, `unknown`) and its evidence.
* **No private data in the repository.** Logs stay on your server. `dba sanitize` strips SSID, MAC, IP, hostnames and keys
  before you share a log; a test scans the repository for such leftovers.

## Quick start (Portainer / Docker)

1. Flash an ESPHome board with firmware that emits Logformat 1 (`docs/LOGFORMAT.md`, examples in `firmware/`: `bshdbus-analysis.example.yaml` for the dishwasher, `macs-analysis.example.yaml` + `macs_recorder.h` for the dryer).
   Enable the API encryption key in ESPHome.
2. In Portainer create a stack (Web editor: paste `docker-compose.yml`; the image `ghcr.io/quidong/device-bus-analyzer:latest` is built by GitHub Actions on every push to `main`) and set these **stack variables** (nothing secret is stored in the repo):

| Variable | Meaning |
|---|---|
| `DBA_DEVICES` | `name@host[:port]/protocol`, comma separated, for example `geschirrspueler@192.0.2.10:6053/bshdbus` |
| `DBA_KEY_<NAME>` | ESPHome API encryption key of that device (`DBA_KEY_GESCHIRRSPUELER`) |
| `ADMIN_EMAIL` | the single admin account (login = e-mail address) |
| `ADMIN_PASSWORD_HASH` | argon2id hash, create with `echo -n 'your password' \| docker run -i --rm ghcr.io/quidong/device-bus-analyzer:latest dba hash-password` |
| `ADMIN_PASSWORD` | alternative to the hash (plain text in the stack; the hash is preferred) |
| `SESSION_SECRET` | 32+ random characters, signs the session cookie |
| `API_TOKEN` | token for the MCP extension and scripts (optional) |
| `DBA_TZ` | display timezone, default `Europe/Berlin` |

3. Open `http://<host>:8080`, sign in. Expose it in your LAN only; there is no password reset and no e-mail sending.
   If you must put it behind a reverse proxy, set `COOKIE_SECURE=1` and terminate TLS there.

Devices that are only online sometimes (a dryer that connects when switched on) are fine: the collector reconnects forever
with back-off and the data model records board restarts and gaps explicitly.

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

`extension/` is a Claude Desktop extension (`.mcpb`, Node). Build it with `cd extension && npm ci --omit=dev && npx @anthropic-ai/mcpb pack`
(the `extension` workflow also builds it on every change) and open the file in Claude Desktop. The install dialog asks for the
**analyzer URL** (for example `http://192.0.2.10:8089`) and the **API token** (`API_TOKEN` of the stack, stored as a sensitive value).
Nine read-only tools: `list_sources`, `get_findings`, `list_runs`, `command_overview`, `command_values`, `timeline`, `frames`,
`raw_bursts`, `data_quality`. Every one is a GET against the read-only API.

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
Open a pull request that changes `spec/<protocol>.yaml` (status + evidence) and, if useful, adds a synthetic test.
Please do not commit logs, MAC/IP addresses, SSIDs or serial numbers.

## Licenses
Code: MIT (`LICENSE`). Protocol documentation and spec files: CC BY 4.0 (`LICENSE-DOCS.md`).
