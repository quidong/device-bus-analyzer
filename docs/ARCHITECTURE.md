# Architecture

| Part | Module | Notes |
|---|---|---|
| Firmware (device side) | `firmware/` | emits Logformat 1: `RAW1` per burst, `HB1` heartbeat every 60 s |
| Log parser | `logformat.py` | tolerant of ANSI colours and host timestamps; detects sequence gaps |
| Protocol decoders | `protocols/` | `bshdbus` (framing + CRC16/XMODEM, ACK, resync), `macs` placeholder |
| Spec | `spec/*.yaml`, `spec.py` | command catalogue with status + evidence, drives decoding and the findings page |
| Storage | `store.py` | SQLite (WAL); raw bursts append-only, frames derived, sessions per board boot, gap table |
| Collector | `collector.py` | aioesphomeapi `subscribe_logs`, reconnect with back-off, never sends |
| Importer | `importer.py` | saved logs, midnight rollover, timezone |
| API + frontend | `web.py`, `auth.py` | single admin from env, argon2id, signed cookie, CSRF, login rate limit, bearer token for API |
| MCP | `mcp_server.py`, `extension/` | stdio server calling the read-only API |

Time: frames get an absolute time from the heartbeat epoch (`boot_epoch = epoch - t_us/1e6`); without it the collector's receive time is used.

Writing to a bus is intentionally not part of this project. If it is ever added it must be a separate, opt-in component with an
allowlist, dry run and ACK verification.
