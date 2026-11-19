"""Group telegrams into runs (one program cycle). Rules come from the spec (`runs:`); detection is derived
and therefore reported with a status (assumed) and its evidence, never as fact."""
from __future__ import annotations

from typing import Any

from .spec import decode, load_spec


def _split_key(key: str) -> tuple[int, int]:
    ds, cmd = key.split("/")
    return int(ds, 16), int(cmd, 16)


def find_runs(db, source_id: int, protocol: str, lock) -> list[dict[str, Any]]:
    """Return runs, newest last. A run starts at the start command and ends at the last telegram before a silent gap
    (or the next start). The newest run is `open` while telegrams keep arriving."""
    spec = load_spec(protocol)
    rules = spec.get("runs") or {}
    if not rules.get("start"):
        return []
    start_ds, start_cmd = _split_key(rules["start"]["key"])
    gap = float(rules.get("end", {}).get("gap_minutes", 20)) * 60
    ctx = float(rules.get("context_seconds", 300))
    prog_ds, prog_cmd = _split_key(rules["program_key"]) if rules.get("program_key") else (None, None)
    rem_ds, rem_cmd = _split_key(rules["remaining_key"]) if rules.get("remaining_key") else (None, None)
    byte, value = rules["start"].get("byte", 0), rules["start"].get("value", 1)

    with lock:
        starts = [dict(r) for r in db.execute(
            "SELECT id, ts, data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND crc_ok=1 ORDER BY ts, id",
            (source_id, start_ds, start_cmd))]
        starts = [s for s in starts if len(s["data"]) > byte and s["data"][byte] == value]
        # one start command is sent several times in a burst series: merge starts that are closer than 60 s
        merged: list[dict] = []
        resume = rules["start"].get("resume_after_state")   # a start while the device is paused resumes the run
        if resume:
            res_ds, res_cmd = _split_key(resume["key"])
        for s in starts:
            if merged and s["ts"] - merged[-1]["last_ts"] < 60:
                merged[-1]["last_ts"] = s["ts"]      # the programme may be chosen between the first and the last start
                continue
            if merged and resume:
                st = db.execute("SELECT data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND ts<? AND ts>=? AND crc_ok=1 "
                                "ORDER BY ts DESC LIMIT 1", (source_id, res_ds, res_cmd, s["ts"], merged[-1]["ts"])).fetchone()
                if st and len(st["data"]) > resume.get("byte", 0) and st["data"][resume.get("byte", 0)] == resume["value"]:
                    merged[-1]["last_ts"] = s["ts"]  # resume after a pause: same run
                    continue
            s["last_ts"] = s["ts"]
            merged.append(s)
        last_ts_all = (db.execute("SELECT MAX(ts) m FROM frames WHERE source_id=?", (source_id,)).fetchone()["m"] or 0)
        runs: list[dict[str, Any]] = []
        for i, s in enumerate(merged):
            limit_ts = merged[i + 1]["ts"] if i + 1 < len(merged) else None
            end_ts, prev, n, bad = s["ts"], s["ts"], 0, 0
            q = "SELECT ts, crc_ok FROM frames WHERE source_id=? AND ts>=?" + (" AND ts<?" if limit_ts else "") + " ORDER BY ts, id"
            args = (source_id, s["ts"], limit_ts) if limit_ts else (source_id, s["ts"])
            ended_by_gap = False
            for r in db.execute(q, args):
                if r["ts"] - prev > gap:
                    ended_by_gap = True
                    break
                prev = end_ts = r["ts"]
                n += 1
                bad += 0 if r["crc_ok"] else 1
            program = None
            if prog_cmd is not None:
                p = db.execute("SELECT ds, cmd, data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND ts<=? AND ts>=? "
                               "AND crc_ok=1 ORDER BY ts DESC LIMIT 1",
                               (source_id, prog_ds, prog_cmd, s["last_ts"], s["ts"] - 3600)).fetchone()
                if p:
                    d = decode(protocol, p["ds"], p["cmd"], p["data"])
                    program = d["values"].get("program")
            rem_start = rem_end = None
            if rem_cmd is not None:
                first = db.execute("SELECT data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND ts>=? AND ts<=? AND crc_ok=1 "
                                   "ORDER BY ts LIMIT 1", (source_id, rem_ds, rem_cmd, s["ts"], end_ts)).fetchone()
                last = db.execute("SELECT data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND ts>=? AND ts<=? AND crc_ok=1 "
                                  "ORDER BY ts DESC LIMIT 1", (source_id, rem_ds, rem_cmd, s["ts"], end_ts)).fetchone()
                rem_start = first["data"][0] if first and first["data"] else None
                rem_end = last["data"][0] if last and last["data"] else None
            is_open = limit_ts is None and not ended_by_gap and (last_ts_all - end_ts) <= gap
            runs.append({
                "id": s["id"], "start_ts": s["ts"], "end_ts": end_ts, "duration_s": round(end_ts - s["ts"], 1),
                "from_ts": max(s["ts"] - ctx, runs[-1]["end_ts"] if runs else 0), "frames": n, "crc_errors": bad,
                "program": program, "remaining_start_min": rem_start, "remaining_end_min": rem_end, "open": is_open,
                "start_status": rules["start"].get("status", "assumed"), "start_evidence": rules["start"].get("evidence", ""),
                "end_status": "unknown" if is_open else rules.get("end", {}).get("status", "assumed"),
                "end_evidence": "run still receiving telegrams" if is_open else rules.get("end", {}).get("evidence", ""),
            })
        return runs
