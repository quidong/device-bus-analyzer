"""Group telegrams into runs (one program cycle). Rules come from the spec (`runs:`); detection is derived
and therefore reported with a status (assumed) and its evidence, never as fact."""
from __future__ import annotations

from typing import Any

from .spec import decode, load_spec


def _split_key(key: str) -> tuple[int, int]:
    ds, cmd = key.split("/")
    return int(ds, 16), int(cmd, 16)


def _matches(data: bytes, rule: dict[str, Any]) -> bool:
    """A frame matches a rule {byte, value | values | nonzero, when?}. ``when`` = {byte, value} selects a layout."""
    when = rule.get("when")
    if when is not None and not (len(data) > when["byte"] and data[when["byte"]] == when["value"]):
        return False
    b = rule.get("byte", 0)
    if len(data) <= b:
        return False
    if rule.get("nonzero"):
        return any(data[b:b + int(rule.get("length", 1))])
    if "values" in rule:
        return data[b] in rule["values"]
    return data[b] == rule.get("value", 1)


def _marker_values(marker: dict[str, Any]) -> list[int]:
    return list(marker["values"]) if "values" in marker else [marker["value"]]


def find_runs(db, source_id: int, protocol: str, lock) -> list[dict[str, Any]]:
    """Return runs, newest last. A run starts at the start command. It ends at the end marker frame when the spec names one
    (``runs.end.marker``, for the BSH D-Bus ``27/2007 = 03``), otherwise, or when the marker frame was lost, at the last
    telegram before a silent gap (or the next start). The newest run is `open` while telegrams keep arriving.

    When the start command itself was not recorded (the board was still booting), ``runs.fallback_start`` names a frame
    that only occurs while a programme runs; the first such frame outside every detected run opens a run whose start is
    marked with the fallback's own status and evidence."""
    spec = load_spec(protocol)
    rules = spec.get("runs") or {}
    if not rules.get("start"):
        return []
    start_ds, start_cmd = _split_key(rules["start"]["key"])
    gap = float(rules.get("end", {}).get("gap_minutes", 20)) * 60
    marker = rules.get("end", {}).get("marker")
    gap_ends_run = bool(rules.get("end", {}).get("gap_ends_run", False))
    mk_ds, mk_cmd = _split_key(marker["key"]) if marker else (None, None)
    mk_values = _marker_values(marker) if marker else []
    ctx = float(rules.get("context_seconds", 300))
    prog_ds, prog_cmd = _split_key(rules["program_key"]) if rules.get("program_key") else (None, None)
    rem_ds, rem_cmd = _split_key(rules["remaining_key"]) if rules.get("remaining_key") else (None, None)
    rem_byte = int(rules.get("remaining_byte", 0))
    rem_when = rules.get("remaining_when")
    byte, value = rules["start"].get("byte", 0), rules["start"].get("value", 1)
    fallback = rules.get("fallback_start")

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
            s["fallback"] = False
            merged.append(s)
        last_ts_all = (db.execute("SELECT MAX(ts) m FROM frames WHERE source_id=?", (source_id,)).fetchone()["m"] or 0)

        def span(start_ts: float, limit_ts: float | None) -> dict[str, Any]:
            """End of the run that starts at ``start_ts`` (marker, gap or the next start), frame and CRC counts."""
            marker_ts = None
            if marker:           # the first intact end-marker frame after the start (and before the next start)
                mq = ("SELECT ts, data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND crc_ok=1 AND ts>?"
                      + (" AND ts<?" if limit_ts else "") + " ORDER BY ts, id")
                margs = (source_id, mk_ds, mk_cmd, start_ts) + ((limit_ts,) if limit_ts else ())
                mb = marker.get("byte", 0)
                for r in db.execute(mq, margs):
                    if len(r["data"]) > mb and r["data"][mb] in mk_values:
                        marker_ts = r["ts"]
                        break
            q = ("SELECT ts, crc_ok FROM frames WHERE source_id=? AND ts>=?"
                 + (" AND ts<?" if limit_ts else "") + (" AND ts<=?" if marker_ts else "") + " ORDER BY ts, id")
            args = (source_id, start_ts) + ((limit_ts,) if limit_ts else ()) + ((marker_ts,) if marker_ts else ())
            end_ts, prev, n, bad, ended_by_gap = start_ts, start_ts, 0, 0, False
            for r in db.execute(q, args):
                # without a marker a silent gap ends the run; with ``end.gap_ends_run`` (a board powered from the bus
                # goes dark when the appliance switches off) it also ends a run whose marker comes only much later
                if r["ts"] - prev > gap and (marker_ts is None or gap_ends_run):
                    ended_by_gap = True
                    marker_ts = None
                    break
                prev = end_ts = r["ts"]
                n += 1
                bad += 0 if r["crc_ok"] else 1
            return {"end_ts": end_ts, "n": n, "bad": bad, "marker_ts": marker_ts, "ended_by_gap": ended_by_gap}

        # Plan B: runs whose start command was not recorded
        if fallback:
            fb_ds, fb_cmd = _split_key(fallback["key"])
            real = [(s["ts"], None) for s in merged]
            spans = []
            for i, s in enumerate(merged):
                lim = merged[i + 1]["ts"] if i + 1 < len(merged) else None
                spans.append((s["ts"], span(s["ts"], lim)["end_ts"]))
            extra: list[dict] = []
            for r in db.execute("SELECT id, ts, data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND crc_ok=1 "
                                "ORDER BY ts, id", (source_id, fb_ds, fb_cmd)):
                if not _matches(r["data"], fallback):
                    continue
                t = r["ts"]
                if any(a - 1 <= t <= b + 1 for a, b in spans):
                    continue
                # a recorded start shortly after belongs to the same programme: its context window shows this frame
                if any(0 <= rt - t <= ctx for rt, _ in real):
                    continue
                nxt = min([a for a, _ in spans if a > t], default=None)
                e = span(t, nxt)
                spans.append((t, e["end_ts"]))
                extra.append({"id": r["id"], "ts": t, "last_ts": t, "data": r["data"], "fallback": True})
            merged = sorted(merged + extra, key=lambda s: s["ts"])

        runs: list[dict[str, Any]] = []
        for i, s in enumerate(merged):
            limit_ts = merged[i + 1]["ts"] if i + 1 < len(merged) else None
            e = span(s["ts"], limit_ts)
            end_ts, n, bad, marker_ts, ended_by_gap = e["end_ts"], e["n"], e["bad"], e["marker_ts"], e["ended_by_gap"]
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
                rows = [r["data"] for r in db.execute(
                    "SELECT data FROM frames WHERE source_id=? AND ds=? AND cmd=? AND ts>=? AND ts<=? AND crc_ok=1 ORDER BY ts, id",
                    (source_id, rem_ds, rem_cmd, s["ts"], end_ts))]
                rows = [d for d in rows if len(d) > rem_byte and (rem_when is None or
                        (len(d) > rem_when["byte"] and d[rem_when["byte"]] == rem_when["value"]))]
                if rows:
                    rem_start, rem_end = rows[0][rem_byte], rows[-1][rem_byte]
            is_open = marker_ts is None and limit_ts is None and not ended_by_gap and (last_ts_all - end_ts) <= gap
            start_rule = fallback if s.get("fallback") else rules["start"]
            runs.append({
                "id": s["id"], "start_ts": s["ts"], "end_ts": end_ts, "duration_s": round(end_ts - s["ts"], 1),
                "from_ts": max(s["ts"] - ctx, runs[-1]["end_ts"] if runs else 0), "frames": n, "crc_errors": bad,
                "program": program, "remaining_start_min": rem_start, "remaining_end_min": rem_end, "open": is_open,
                "start_by": "fallback" if s.get("fallback") else "command",
                "start_status": start_rule.get("status", "assumed"), "start_evidence": start_rule.get("evidence", ""),
                "end_by": "marker" if marker_ts else ("open" if is_open else "gap"),
                "end_status": ("unknown" if is_open else marker.get("status", "assumed") if marker_ts
                               else rules.get("end", {}).get("status", "assumed")),
                "end_evidence": ("run still receiving telegrams" if is_open else marker.get("evidence", "") if marker_ts
                                 else rules.get("end", {}).get("evidence", "")),
            })
        return runs
