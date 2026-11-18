"""SQLite storage. Raw bursts are append-only; frames are derived and can be rebuilt at any time."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from . import logformat, protocols
from . import runs as runs_mod
from .spec import decode

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

    def close(self):
        with self.lock:
            self.db.close()

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
                "SELECT s.id, s.name, s.protocol,"
                " (SELECT COUNT(*) FROM bursts b JOIN sessions x ON x.id=b.session_id WHERE x.source_id=s.id) AS bursts,"
                " (SELECT COUNT(*) FROM frames f WHERE f.source_id=s.id) AS frames,"
                " (SELECT MIN(ts) FROM frames f WHERE f.source_id=s.id) AS first_ts,"
                " (SELECT MAX(ts) FROM frames f WHERE f.source_id=s.id) AS last_ts"
                " FROM sources s ORDER BY s.name").fetchall()
        return [dict(r) for r in rows]

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
                self.db.execute(
                    "INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) VALUES(?,?,?,?,?,?,?,?,?)",
                    (source_id, None, None, recv_ts, e["ds"], e["cmd"], e["data"], int(e["crc_ok"]), e["ack"]))
            self.db.commit()
        return e["typ"]

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
