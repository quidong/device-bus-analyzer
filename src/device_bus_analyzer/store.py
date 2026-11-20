"""SQLite storage. Raw bursts are append-only; frames are derived and can be rebuilt at any time."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from . import logformat, protocols
from . import runs as runs_mod
from .config import Device
from .spec import decode

log = logging.getLogger("dba.store")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, protocol TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(            -- one per board boot
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id),
  started_recv REAL NOT NULL, boot_epoch REAL, last_t_us INTEGER NOT NULL DEFAULT 0, last_seq INTEGER);
CREATE TABLE IF NOT EXISTS bursts(
  id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
  seq INTEGER, t_us INTEGER, dt_us INTEGER, recv_ts REAL, data BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS ix_bursts_session ON bursts(session_id, t_us);
CREATE TABLE IF NOT EXISTS frames(
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, session_id INTEGER, burst_id INTEGER,
  ts REAL NOT NULL, ds INTEGER NOT NULL, cmd INTEGER NOT NULL, data BLOB NOT NULL,
  crc_ok INTEGER NOT NULL, ack INTEGER);
CREATE INDEX IF NOT EXISTS ix_frames_src_ts ON frames(source_id, ts);
CREATE INDEX IF NOT EXISTS ix_frames_key ON frames(source_id, ds, cmd, ts);
CREATE TABLE IF NOT EXISTS heartbeats(
  id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, seq INTEGER, t_us INTEGER, epoch INTEGER,
  bytes INTEGER, bursts INTEGER, ok INTEGER, crc INTEGER, noack INTEGER, rest INTEGER, recv_ts REAL);
CREATE TABLE IF NOT EXISTS gaps(
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, session_id INTEGER, recv_ts REAL, message TEXT NOT NULL);
-- Added with device management. Purely additive: existing tables and rows are never altered or dropped.
CREATE TABLE IF NOT EXISTS devices(             -- classification + connection of a source; no row = imported / unclassified
  source_id INTEGER PRIMARY KEY REFERENCES sources(id),
  type TEXT, manufacturer TEXT, model TEXT,
  host TEXT, port INTEGER NOT NULL DEFAULT 6053, key TEXT,   -- key: ESPHome API encryption key, never leaves the server
  enabled INTEGER NOT NULL DEFAULT 1, created_ts REAL NOT NULL, updated_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- small app settings (knowledge update state)
-- Last time the collector held a live connection to the device (an idle appliance sends no telegrams, but is online).
CREATE TABLE IF NOT EXISTS contact(source_id INTEGER PRIMARY KEY, ts REAL NOT NULL);
-- Added with the companion mode (again purely additive). Markers are what the person did at the appliance, timed by the server.
CREATE TABLE IF NOT EXISTS markers(
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, ts REAL NOT NULL, ts_end REAL,   -- ts_end set = an action with a duration
  kind TEXT NOT NULL, label TEXT NOT NULL, menu TEXT, note TEXT, step_group TEXT);
CREATE INDEX IF NOT EXISTS ix_markers_src ON markers(source_id, ts);
CREATE TABLE IF NOT EXISTS learned(               -- findings the person accepted from the analysis (local, per device)
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, meaning TEXT NOT NULL, kind TEXT, ds INTEGER, cmd INTEGER, pos INTEGER,
  from_val INTEGER, to_val INTEGER, hits INTEGER, n INTEGER, status TEXT NOT NULL, created_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS learned_values(        -- numbers that follow what the display shows (remaining time, temperature ...)
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, meaning TEXT NOT NULL, unit TEXT, ds INTEGER, cmd INTEGER, pos INTEGER,
  enc TEXT NOT NULL, factor REAL NOT NULL, interp TEXT, hits INTEGER, n INTEGER, status TEXT NOT NULL, created_ts REAL NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)
        self._sessions: dict[int, dict] = {}
        self._pending_rx: dict[int, list] = {}

    def close(self):
        with self.lock:
            self.db.close()

    # --- backup / restore ---------------------------------------------------------
    REQUIRED_TABLES = ("sources", "sessions", "bursts", "frames", "devices")

    def backup_to(self, path: str | Path) -> None:
        """Consistent snapshot of the live database (SQLite backup API; safe while the collectors write)."""
        dst = sqlite3.connect(str(path))
        try:
            with self.lock:
                self.db.backup(dst)
        finally:
            dst.close()

    @classmethod
    def check_backup(cls, path: str | Path) -> str | None:
        """None if the file is a usable snapshot, otherwise a short reason."""
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    return "integrity"
                # data only: a file with triggers, views or virtual tables could run SQL of its own once restored
                if con.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR sql LIKE 'CREATE VIRTUAL%' LIMIT 1").fetchone():
                    return "active_content"
                have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                con.close()
        except sqlite3.Error:
            return "not_sqlite"
        return None if all(t in have for t in cls.REQUIRED_TABLES) else "missing_tables"

    def restore_from(self, path: str | Path) -> None:
        """Replace the content of the live database with a checked snapshot; missing newer tables are added afterwards."""
        src = sqlite3.connect(str(path))
        try:
            with self.lock:
                src.backup(self.db)
                self.db.executescript(SCHEMA)
                self._sessions.clear()
                self._pending_rx.clear()
        finally:
            src.close()

    # --- sources ------------------------------------------------------------
    def source(self, name: str, protocol: str) -> int:
        protocols.get(protocol)
        with self.lock:
            row = self.db.execute("SELECT id, protocol FROM sources WHERE name=?", (name,)).fetchone()
            if row:
                if row["protocol"] != protocol:
                    raise ValueError(f"source {name!r} is stored with protocol {row['protocol']!r} but was requested with {protocol!r}")
                return row["id"]
            cur = self.db.execute("INSERT INTO sources(name, protocol) VALUES(?,?)", (name, protocol))
            self.db.commit()
            return cur.lastrowid

    def sources(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT s.id, s.name, s.protocol, d.type, d.manufacturer, d.model,"
                " (SELECT COUNT(*) FROM bursts b JOIN sessions x ON x.id=b.session_id WHERE x.source_id=s.id) AS bursts,"
                " (SELECT COUNT(*) FROM frames f WHERE f.source_id=s.id) AS frames,"
                " (SELECT MIN(ts) FROM frames f WHERE f.source_id=s.id) AS first_ts,"
                " (SELECT MAX(ts) FROM frames f WHERE f.source_id=s.id) AS last_ts"
                " FROM sources s LEFT JOIN devices d ON d.source_id=s.id ORDER BY s.name").fetchall()
        return [dict(r) for r in rows]

    # --- devices (classification + connection) ------------------------------------
    def kv_get(self, key: str, default: str | None = None) -> str | None:
        with self.lock:
            r = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def kv_set(self, key: str, value: str) -> None:
        with self.lock:
            self.db.execute("INSERT INTO kv(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
            self.db.commit()

    def touch_contact(self, source_id: int, ts: float | None = None) -> None:
        with self.lock:
            self.db.execute("INSERT INTO contact(source_id, ts) VALUES(?,?) ON CONFLICT(source_id) DO UPDATE SET ts=excluded.ts",
                            (source_id, time.time() if ts is None else ts))
            self.db.commit()

    def devices(self) -> list[dict]:
        """All sources with their device row, without the key (only whether one is set)."""
        rows = self._q(
            "SELECT s.name, s.protocol, d.type, d.manufacturer, d.model, d.host, d.port, d.enabled, d.key IS NOT NULL AND d.key<>'' AS has_key,"
            " d.source_id IS NOT NULL AS configured,"
            " (SELECT COUNT(*) FROM frames f WHERE f.source_id=s.id) AS frames,"
            # last sign of life: live connection, newest heartbeat, or the newest burst of the latest board session
            " MAX(COALESCE((SELECT c.ts FROM contact c WHERE c.source_id=s.id), 0), COALESCE((SELECT MAX(h.recv_ts) FROM heartbeats h JOIN sessions x ON x.id=h.session_id WHERE x.source_id=s.id), 0),"
            "     COALESCE((SELECT x.started_recv + x.last_t_us/1e6 FROM sessions x WHERE x.source_id=s.id ORDER BY x.id DESC LIMIT 1), 0)) AS last_seen"
            " FROM sources s LEFT JOIN devices d ON d.source_id=s.id ORDER BY s.name")
        for r in rows:
            r["last_seen"] = r["last_seen"] or None
            r["has_key"], r["configured"] = bool(r["has_key"]), bool(r["configured"])
            r["enabled"] = bool(r["enabled"]) if r["enabled"] is not None else False
        return rows

    def data_counts(self, name: str) -> dict[str, int] | None:
        """How much would be removed with this device (for the confirmation page)."""
        src = self.source_by_name(name)
        if not src:
            return None
        one = lambda sql: self._q(sql, (src["id"],))[0]["n"]               # noqa: E731
        return {"bursts": one("SELECT COUNT(*) n FROM bursts WHERE session_id IN (SELECT id FROM sessions WHERE source_id=?)"),
                "frames": one("SELECT COUNT(*) n FROM frames WHERE source_id=?"),
                "heartbeats": one("SELECT COUNT(*) n FROM heartbeats WHERE session_id IN (SELECT id FROM sessions WHERE source_id=?)"),
                "sessions": one("SELECT COUNT(*) n FROM sessions WHERE source_id=?"),
                "gaps": one("SELECT COUNT(*) n FROM gaps WHERE source_id=?"),
                "markers": one("SELECT COUNT(*) n FROM markers WHERE source_id=?"),
                "learned": one("SELECT COUNT(*) n FROM learned WHERE source_id=?") + one("SELECT COUNT(*) n FROM learned_values WHERE source_id=?")}

    def delete_device(self, name: str) -> dict[str, int] | None:
        """Remove a source completely: raw bursts, frames, runs (derived), heartbeats, gaps, sessions, connection and key.
        Irreversible; one transaction. Returns what was removed, or None for an unknown name."""
        with self.lock:
            counts = self.data_counts(name)
            if counts is None:
                return None
            sid = self.source_by_name(name)["id"]
            try:
                self.db.execute("DELETE FROM bursts WHERE session_id IN (SELECT id FROM sessions WHERE source_id=?)", (sid,))
                self.db.execute("DELETE FROM heartbeats WHERE session_id IN (SELECT id FROM sessions WHERE source_id=?)", (sid,))
                self.db.execute("DELETE FROM frames WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM gaps WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM markers WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM learned WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM learned_values WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM contact WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM sessions WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM devices WHERE source_id=?", (sid,))
                self.db.execute("DELETE FROM sources WHERE id=?", (sid,))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            self._sessions.pop(sid, None)
            self._pending_rx.pop(sid, None)
            try:
                self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")          # give the WAL space back; freed pages are reused by new data
            except sqlite3.Error:
                pass
        log.info("device %s deleted: %s", name, counts)
        return counts

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Pause or resume the collection of a configured device. Data is untouched."""
        with self.lock:
            cur = self.db.execute("UPDATE devices SET enabled=?, updated_ts=? WHERE source_id=(SELECT id FROM sources WHERE name=?)",
                                  (int(enabled), time.time(), name))
            self.db.commit()
            return cur.rowcount > 0

    def device(self, name: str) -> dict | None:
        return next((d for d in self.devices() if d["name"] == name), None)

    def used_classifications(self) -> list[dict]:
        return self._q("SELECT d.type, d.manufacturer, d.model, s.protocol FROM devices d JOIN sources s ON s.id=d.source_id")

    def save_device(self, name: str, protocol: str, type: str | None, manufacturer: str | None, model: str | None,
                    host: str | None, port: int = 6053, key: str | None = None, clear_key: bool = False,
                    enabled: bool = True) -> int:
        """Create or update the device row of a source (creating the source if needed; an existing source keeps its id and data).

        ``key=None`` keeps a stored key, ``clear_key`` removes it. The protocol of an existing source cannot change."""
        source_id = self.source(name, protocol)          # raises on protocol mismatch with stored data
        now = time.time()
        with self.lock:
            row = self.db.execute("SELECT key FROM devices WHERE source_id=?", (source_id,)).fetchone()
            new_key = None if clear_key else (key if key is not None else (row["key"] if row else None))
            if row is None:
                self.db.execute("INSERT INTO devices(source_id, type, manufacturer, model, host, port, key, enabled, created_ts, updated_ts)"
                                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (source_id, type, manufacturer, model, host, port, new_key, int(enabled), now, now))
            else:
                self.db.execute("UPDATE devices SET type=?, manufacturer=?, model=?, host=?, port=?, key=?, enabled=?, updated_ts=?"
                                " WHERE source_id=?", (type, manufacturer, model, host, port, new_key, int(enabled), now, source_id))
            self.db.commit()
        return source_id

    def connections(self) -> list[Device]:
        """Enabled devices that have a host: what the collector should connect to."""
        rows = self._q("SELECT s.name, s.protocol, d.host, d.port, d.key FROM devices d JOIN sources s ON s.id=d.source_id"
                       " WHERE d.enabled=1 AND d.host IS NOT NULL AND d.host<>'' ORDER BY s.name")
        return [Device(r["name"], r["host"], r["port"], r["protocol"], r["key"] or None) for r in rows]

    def seed_devices(self, devices: Iterable[Device]) -> list[str]:
        """One-time import of the former environment configuration (DBA_DEVICES / DBA_KEY_<NAME>).

        Idempotent and never overwrites: a device that already has a row keeps everything the user set in the UI; only a missing
        key is filled in. Returns the names that were created."""
        created = []
        for d in devices:
            try:
                existing = self._q("SELECT d.source_id, d.key FROM devices d JOIN sources s ON s.id=d.source_id WHERE s.name=?", (d.name,))
                if existing:
                    if d.key and not existing[0]["key"]:
                        with self.lock:
                            self.db.execute("UPDATE devices SET key=?, updated_ts=? WHERE source_id=?", (d.key, time.time(), existing[0]["source_id"]))
                            self.db.commit()
                    continue
                self.save_device(d.name, d.protocol, None, None, None, d.host, d.port, d.key)
                created.append(d.name)
            except ValueError as exc:                    # e.g. protocol differs from the one stored for that name: keep the data, skip
                log.warning("device %s from the environment not imported: %s", d.name, exc)
        return created

    # --- sessions -----------------------------------------------------------
    def _session(self, source_id: int, t_us: int | None, recv_ts: float) -> dict:
        cur = self._sessions.get(source_id)
        if cur is None:
            row = self.db.execute("SELECT * FROM sessions WHERE source_id=? ORDER BY id DESC LIMIT 1", (source_id,)).fetchone()
            cur = dict(row) if row else None
        if cur is not None and (t_us is None or t_us >= cur["last_t_us"]):
            cur["last_t_us"] = max(cur["last_t_us"], t_us or 0)
            self._sessions[source_id] = cur
            return cur
        c = self.db.execute("INSERT INTO sessions(source_id, started_recv, last_t_us) VALUES(?,?,?)",
                            (source_id, recv_ts, t_us or 0))
        cur = {"id": c.lastrowid, "source_id": source_id, "started_recv": recv_ts, "boot_epoch": None,
               "last_t_us": t_us or 0, "last_seq": None}
        self._sessions[source_id] = cur
        return cur

    def _ts(self, sess: dict, t_us: int | None, recv_ts: float) -> float:
        if sess["boot_epoch"] is not None and t_us is not None:
            return sess["boot_epoch"] + t_us / 1e6
        return recv_ts

    # --- ingest -------------------------------------------------------------
    def ingest_line(self, source_id: int, line: str, recv_ts: float | None = None) -> str | None:
        """Store one log line. Returns the line type ('RAW1', 'HB1', ...) or None if it was not relevant."""
        e = logformat.parse_line(line)
        if e is None:
            return None
        recv_ts = recv_ts if recv_ts is not None else time.time()
        if "fehler" in e:
            with self.lock:
                self.db.execute("INSERT INTO gaps(source_id, recv_ts, message) VALUES(?,?,?)",
                                (source_id, recv_ts, "broken RAW1 line: " + e["fehler"]))
                self.db.commit()
            return "BROKEN"
        with self.lock:
            if e["typ"] == "RAW1":
                self._ingest_raw(source_id, e, recv_ts)
            elif e["typ"] == "HB1":
                self._ingest_hb(source_id, e, recv_ts)
            else:                                    # legacy FRAME / RECEIVED: frames only, no raw burst
                self._ingest_legacy(source_id, e, recv_ts)
            self.db.commit()
        return e["typ"]

    def _ingest_legacy(self, source_id: int, e: dict, recv_ts: float) -> None:
        """The same frame is logged twice by the old firmware: 'Received frame ...' (component) and 'FRAME ...' (dbus_raw,
        with ACK info). A FRAME line replaces the RECEIVED row of the same bytes logged within 2 s before it."""
        key = (e["ds"], e["cmd"], bytes(e["data"]))
        pend = self._pending_rx.setdefault(source_id, [])
        pend[:] = [p for p in pend if recv_ts - p[2] <= 2.0]
        if e["typ"] == "FRAME":
            for i, (rid, k, _t) in enumerate(pend):
                if k == key:
                    self.db.execute("DELETE FROM frames WHERE id=?", (rid,))
                    del pend[i]
                    break
        cur = self.db.execute(
            "INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) VALUES(?,?,?,?,?,?,?,?,?)",
            (source_id, None, None, recv_ts, e["ds"], e["cmd"], e["data"], int(e["crc_ok"]), e["ack"]))
        if e["typ"] == "RECEIVED":
            pend.append((cur.lastrowid, key, recv_ts))

    def _proto(self, source_id: int):
        name = self.db.execute("SELECT protocol FROM sources WHERE id=?", (source_id,)).fetchone()["protocol"]
        return protocols.get(name)

    def _ingest_raw(self, source_id: int, e: dict, recv_ts: float) -> None:
        sess = self._session(source_id, e["t_us"], recv_ts)
        if sess["last_seq"] is not None and e["seq"] != sess["last_seq"] + 1 and e["seq"] > sess["last_seq"]:
            self.db.execute("INSERT INTO gaps(source_id, session_id, recv_ts, message) VALUES(?,?,?,?)",
                            (source_id, sess["id"], recv_ts,
                             f"seq {sess['last_seq']} -> {e['seq']} ({e['seq'] - sess['last_seq'] - 1} bursts missing)"))
        sess["last_seq"] = e["seq"]
        self.db.execute("UPDATE sessions SET last_t_us=?, last_seq=? WHERE id=?", (sess["last_t_us"], e["seq"], sess["id"]))
        cur = self.db.execute("INSERT INTO bursts(session_id, seq, t_us, dt_us, recv_ts, data) VALUES(?,?,?,?,?,?)",
                              (sess["id"], e["seq"], e["t_us"], e["dt_us"], recv_ts, e["data"]))
        self._insert_frames(source_id, sess, cur.lastrowid, e["t_us"], recv_ts, e["data"])

    def _insert_frames(self, source_id: int, sess: dict, burst_id: int, t_us: int, recv_ts: float, data: bytes) -> None:
        frames, _ = self._proto(source_id).parse_burst(data)
        ts = self._ts(sess, t_us, recv_ts)
        self.db.executemany(
            "INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) VALUES(?,?,?,?,?,?,?,?,?)",
            [(source_id, sess["id"], burst_id, ts, f.ds, f.cmd, f.data, int(f.crc_ok), f.ack) for f in frames])

    def _ingest_hb(self, source_id: int, e: dict, recv_ts: float) -> None:
        sess = self._session(source_id, e["t_us"], recv_ts)
        if e["epoch"] and sess["boot_epoch"] is None:
            sess["boot_epoch"] = e["epoch"] - e["t_us"] / 1e6
            self.db.execute("UPDATE sessions SET boot_epoch=? WHERE id=?", (sess["boot_epoch"], sess["id"]))
        if sess["last_seq"] is not None and e["seq"] > sess["last_seq"]:
            self.db.execute("INSERT INTO gaps(source_id, session_id, recv_ts, message) VALUES(?,?,?,?)",
                            (source_id, sess["id"], recv_ts,
                             f"heartbeat seq={e['seq']}, last seen seq={sess['last_seq']}: bursts lost"))
            sess["last_seq"] = e["seq"]
        self.db.execute(
            "INSERT INTO heartbeats(session_id, seq, t_us, epoch, bytes, bursts, ok, crc, noack, rest, recv_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sess["id"], e["seq"], e["t_us"], e["epoch"], e["bytes"], e["bursts"], e["ok"], e["crc"], e["noack"], e["rest"], recv_ts))

    def rebuild_frames(self, source_id: int | None = None) -> int:
        """Re-derive frames from raw bursts, for example after the decoder improved. Raw data is never touched."""
        n = 0
        with self.lock:
            srcs = [source_id] if source_id else [r["id"] for r in self.db.execute("SELECT id FROM sources")]
            for sid in srcs:
                self.db.execute("DELETE FROM frames WHERE source_id=? AND burst_id IS NOT NULL", (sid,))
                rows = self.db.execute(
                    "SELECT b.id, b.session_id, b.t_us, b.recv_ts, b.data, s.boot_epoch FROM bursts b "
                    "JOIN sessions s ON s.id=b.session_id WHERE s.source_id=? ORDER BY b.id", (sid,)).fetchall()
                for r in rows:
                    sess = {"id": r["session_id"], "boot_epoch": r["boot_epoch"]}
                    self._insert_frames(sid, sess, r["id"], r["t_us"], r["recv_ts"], r["data"])
                    n += 1
            self.db.commit()
        return n

    # --- companion: markers and accepted findings --------------------------------------------------------
    def add_marker(self, name: str, kind: str, label: str, menu: str | None = None, note: str | None = None,
                   ts: float | None = None, ts_end: float | None = None, step_group: str | None = None) -> dict | None:
        src = self.source_by_name(name)
        if not src:
            return None
        clean = lambda v, n: (v or "").strip()[:n] or None                      # noqa: E731
        kind, label = (clean(kind, 40), clean(label, 80))
        if not kind or not label:
            raise ValueError("kind and label are required")
        ts = time.time() if ts is None else ts
        with self.lock:
            c = self.db.execute("INSERT INTO markers(source_id, ts, ts_end, kind, label, menu, note, step_group) VALUES(?,?,?,?,?,?,?,?)",
                                (src["id"], ts, ts_end, kind, label, clean(menu, 80), clean(note, 200), clean(step_group, 40)))
            self.db.commit()
        return self.marker(name, c.lastrowid)

    def marker(self, name: str, marker_id: int) -> dict | None:
        r = self.markers(name, marker_id=marker_id)
        return r[0] if r else None

    def markers(self, name: str, since: float | None = None, until: float | None = None, limit: int = 500,
                marker_id: int | None = None, newest_first: bool = False) -> list[dict]:
        src = self.source_by_name(name)
        if not src:
            return []
        w, a = ["source_id=?"], [src["id"]]
        for sql, v in (("id=?", marker_id), ("COALESCE(ts_end, ts)>=?", since), ("ts<=?", until)):
            if v is not None:
                w.append(sql); a.append(v)
        order = "DESC" if newest_first else "ASC"
        return self._q(f"SELECT id, ts, ts_end, kind, label, menu, note, step_group FROM markers WHERE {' AND '.join(w)} "
                       f"ORDER BY ts {order}, id {order} LIMIT ?", [*a, min(limit, 5000)])

    def end_marker(self, name: str, marker_id: int, ts_end: float | None = None, note: str | None = None,
                   label: str | None = None) -> dict | None:
        """Close an action that has a duration; the note (what the display showed, which option) may only be known now."""
        m = self.marker(name, marker_id)
        if not m:
            return None
        note = (note or "").strip()[:200] or m["note"]
        label = (label or "").strip()[:80] or m["label"]
        with self.lock:
            self.db.execute("UPDATE markers SET ts_end=?, note=?, label=? WHERE id=? AND source_id=(SELECT id FROM sources WHERE name=?)",
                            (max(m["ts"], time.time() if ts_end is None else ts_end), note, label, marker_id, name))
            self.db.commit()
        return self.marker(name, marker_id)

    def delete_marker(self, name: str, marker_id: int) -> bool:
        with self.lock:
            c = self.db.execute("DELETE FROM markers WHERE id=? AND source_id=(SELECT id FROM sources WHERE name=?)", (marker_id, name))
            self.db.commit()
        return c.rowcount > 0

    def frame_series(self, name: str, lo: float, hi: float, limit: int = 400_000) -> dict[tuple[int, int], tuple[list[float], list[bytes]]]:
        """Valid frames in [lo, hi] as {(ds, cmd): (timestamps, payloads)}, in time order. The input of the analysis."""
        src = self.source_by_name(name)
        out: dict[tuple[int, int], tuple[list[float], list[bytes]]] = {}
        if not src:
            return out
        with self.lock:
            cur = self.db.execute("SELECT ts, ds, cmd, data FROM frames WHERE source_id=? AND crc_ok=1 AND ts BETWEEN ? AND ? "
                                  "ORDER BY ts, id LIMIT ?", (src["id"], lo, hi, limit))
            for r in cur:
                t, d = out.setdefault((r["ds"], r["cmd"]), ([], []))
                t.append(r["ts"]); d.append(bytes(r["data"]))
        return out

    def save_learned(self, name: str, meaning: str, kind: str, ds: int, cmd: int, pos: int, from_val: int | None, to_val: int | None,
                     hits: int, n: int, status: str) -> int | None:
        src = self.source_by_name(name)
        if not src:
            return None
        with self.lock:
            c = self.db.execute("INSERT INTO learned(source_id, meaning, kind, ds, cmd, pos, from_val, to_val, hits, n, status, created_ts) "
                                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (src["id"], meaning.strip()[:120], kind, ds, cmd, pos, from_val, to_val,
                                                                     hits, n, status, time.time()))
            self.db.commit()
        return c.lastrowid

    def learned(self, name: str) -> list[dict]:
        src = self.source_by_name(name)
        return self._q("SELECT id, meaning, kind, ds, cmd, pos, from_val, to_val, hits, n, status, created_ts FROM learned "
                       "WHERE source_id=? ORDER BY ds, cmd, pos, id", (src["id"],)) if src else []

    def save_learned_value(self, name: str, meaning: str, unit: str | None, ds: int, cmd: int, pos: int, enc: str, factor: float,
                           interp: str, hits: int, n: int, status: str) -> int | None:
        src = self.source_by_name(name)
        if not src:
            return None
        with self.lock:
            c = self.db.execute("INSERT INTO learned_values(source_id, meaning, unit, ds, cmd, pos, enc, factor, interp, hits, n, status, created_ts) "
                                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (src["id"], meaning.strip()[:120], (unit or "").strip()[:12] or None, ds, cmd, pos,
                                                                       enc, factor, interp, hits, n, status, time.time()))
            self.db.commit()
        return c.lastrowid

    def learned_values(self, name: str) -> list[dict]:
        src = self.source_by_name(name)
        return self._q("SELECT id, meaning, unit, ds, cmd, pos, enc, factor, interp, hits, n, status FROM learned_values WHERE source_id=? "
                       "ORDER BY ds, cmd, pos, id", (src["id"],)) if src else []

    def delete_learned_value(self, name: str, value_id: int) -> bool:
        with self.lock:
            c = self.db.execute("DELETE FROM learned_values WHERE id=? AND source_id=(SELECT id FROM sources WHERE name=?)", (value_id, name))
            self.db.commit()
        return c.rowcount > 0

    def latest_payload(self, name: str, ds: int, cmd: int) -> tuple[float, bytes] | None:
        """Newest valid payload of one command (for 'the state right now')."""
        src = self.source_by_name(name)
        rows = self._q("SELECT ts, data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND crc_ok=1 ORDER BY ts DESC, id DESC LIMIT 1",
                       (src["id"], ds, cmd)) if src else []
        return (rows[0]["ts"], bytes(rows[0]["data"])) if rows else None

    def delete_learned(self, name: str, learned_id: int) -> bool:
        with self.lock:
            c = self.db.execute("DELETE FROM learned WHERE id=? AND source_id=(SELECT id FROM sources WHERE name=?)", (learned_id, name))
            self.db.commit()
        return c.rowcount > 0

    # --- queries (read-only) ------------------------------------------------
    def _q(self, sql: str, args: Iterable[Any] = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, tuple(args)).fetchall()]

    def source_by_name(self, name: str) -> dict | None:
        r = self._q("SELECT * FROM sources WHERE name=?", (name,))
        return r[0] if r else None

    def frames(self, source: str, ds: int | None = None, cmd: int | None = None, since: float | None = None,
               until: float | None = None, crc_ok: bool | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
        src = self.source_by_name(source)
        if not src:
            return []
        w, a = ["source_id=?"], [src["id"]]
        for col, val in (("ds", ds), ("cmd", cmd)):
            if val is not None:
                w.append(f"{col}=?"); a.append(val)
        if since is not None:
            w.append("ts>=?"); a.append(since)
        if until is not None:
            w.append("ts<=?"); a.append(until)
        if crc_ok is not None:
            w.append("crc_ok=?"); a.append(int(crc_ok))
        rows = self._q(f"SELECT id, ts, ds, cmd, data, crc_ok, ack, burst_id FROM frames WHERE {' AND '.join(w)} "
                       f"ORDER BY ts, id LIMIT ? OFFSET ?", [*a, min(limit, 5000), offset])
        proto = src["protocol"]
        for r in rows:
            r["decoded"] = decode(proto, r["ds"], r["cmd"], r["data"], r["ack"])
        return rows

    def timeline(self, source: str, since: float | None = None, until: float | None = None, limit: int = 2000) -> list[dict]:
        """Only value changes per (ds, cmd): what is needed to understand a run."""
        src = self.source_by_name(source)
        if not src:
            return []
        w, a = ["source_id=?", "crc_ok=1"], [src["id"]]
        if since is not None:
            w.append("ts>=?"); a.append(since)
        if until is not None:
            w.append("ts<=?"); a.append(until)
        last, out = {}, []
        with self.lock:
            cur = self.db.execute(f"SELECT ts, ds, cmd, data FROM frames WHERE {' AND '.join(w)} ORDER BY ts, id", a)
            for r in cur:
                k = (r["ds"], r["cmd"])
                if last.get(k) != r["data"]:
                    last[k] = r["data"]
                    d = decode(src["protocol"], r["ds"], r["cmd"], r["data"])
                    out.append({"ts": r["ts"], "ds": r["ds"], "cmd": r["cmd"], "data": r["data"], "decoded": d})
                    if len(out) >= limit:
                        break
        return out

    def runs(self, source: str) -> list[dict]:
        src = self.source_by_name(source)
        return runs_mod.find_runs(self.db, src["id"], src["protocol"], self.lock) if src else []

    def run(self, source: str, run_id: int) -> dict | None:
        return next((r for r in self.runs(source) if r["id"] == run_id), None)

    def command_stats(self, source: str) -> list[dict]:
        src = self.source_by_name(source)
        if not src:
            return []
        rows = self._q("SELECT ds, cmd, COUNT(*) n, COUNT(DISTINCT data) distinct_values, MIN(ts) first_ts, MAX(ts) last_ts, "
                       "SUM(crc_ok) ok FROM frames WHERE source_id=? GROUP BY ds, cmd ORDER BY ds, cmd", (src["id"],))
        for r in rows:
            r["decoded"] = decode(src["protocol"], r["ds"], r["cmd"], b"")
        return rows

    def command_values(self, source: str, ds: int, cmd: int, limit: int = 50) -> list[dict]:
        src = self.source_by_name(source)
        if not src:
            return []
        return self._q("SELECT data, COUNT(*) n, MIN(ts) first_ts, MAX(ts) last_ts FROM frames WHERE source_id=? AND ds=? AND cmd=? "
                       "AND crc_ok=1 GROUP BY data ORDER BY n DESC LIMIT ?", (src["id"], ds, cmd, limit))

    def bursts(self, source: str, since: float | None = None, until: float | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
        src = self.source_by_name(source)
        if not src:
            return []
        w, a = ["s.source_id=?"], [src["id"]]
        if since is not None:
            w.append("COALESCE(s.boot_epoch + b.t_us/1e6, b.recv_ts)>=?"); a.append(since)
        if until is not None:
            w.append("COALESCE(s.boot_epoch + b.t_us/1e6, b.recv_ts)<=?"); a.append(until)
        return self._q("SELECT b.id, b.seq, b.t_us, b.dt_us, COALESCE(s.boot_epoch + b.t_us/1e6, b.recv_ts) AS ts, b.data "
                       f"FROM bursts b JOIN sessions s ON s.id=b.session_id WHERE {' AND '.join(w)} ORDER BY b.id LIMIT ? OFFSET ?",
                       [*a, min(limit, 5000), offset])

    def quality(self, source: str) -> dict:
        src = self.source_by_name(source)
        if not src:
            return {}
        f = self._q("SELECT COUNT(*) n, SUM(crc_ok) ok, SUM(crc_ok=1 AND ack IS NULL) noack FROM frames WHERE source_id=?", (src["id"],))[0]
        g = self._q("SELECT recv_ts, message FROM gaps WHERE source_id=? ORDER BY id DESC LIMIT 50", (src["id"],))
        s = self._q("SELECT COUNT(*) n FROM sessions WHERE source_id=?", (src["id"],))[0]["n"]
        return {"frames": f["n"], "ok": f["ok"] or 0, "crc_errors": f["n"] - (f["ok"] or 0), "ok_without_ack": f["noack"] or 0,
                "sessions": s, "gaps": g}
