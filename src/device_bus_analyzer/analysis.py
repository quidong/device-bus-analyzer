"""Companion analysis: which bytes change when the person does something at the appliance?

Input: the markers (what was done, when, timed by the server) and the stored frames. Nothing is sent anywhere.

For every marker the state of each (dest, command) payload just before is compared with the state just after. Bytes that change
become candidates. Three safeguards keep it honest:

* **Noise model.** Counters, timers and sensor values change on their own. The same comparison is run on quiet windows
  (no marker nearby); a byte that changes in many of those is penalised and can never be confirmed.
* **Repeats.** A candidate only counts when it shows up again and again for the same action (hits / n).
* **Pairs.** Door open / door closed (and other opposite actions) must flip the same byte back and forth. Only then is a
  candidate 'confirmed'; consistent repeats alone give 'assumed'.

Everything here is a pure function of its inputs, so it is easy to test with synthetic frames.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from typing import Any

PRE = 3.0          # seconds before an instant marker that may already belong to the action (pressed, then tapped)
POST = 6.0         # seconds after an instant marker in which the bus reacts
SLACK_START = 1.0  # same for actions with a duration (start / end tap)
SLACK_END = 2.0
NOISE_WINDOW = PRE + POST
MIN_BASELINE = 5   # fewer quiet windows than this: the noise is unknown and nothing is confirmed
MAX_BASELINE = 300
MAX_NOISE = {"assumed": 0.25, "confirmed": 0.10, "unpaired": 0.05}

Series = dict[tuple[int, int], tuple[list[float], list[bytes]]]


def _state_at(series: tuple[list[float], list[bytes]], t: float) -> bytes | None:
    i = bisect_right(series[0], t)
    return series[1][i - 1] if i else None


def _changed(a: bytes | None, b: bytes | None) -> list[int]:
    """Positions that differ; [-1] means the length changed (a different layout, not one byte)."""
    if a is None or b is None or a == b:
        return []
    if len(a) != len(b):
        return [-1]
    return [i for i in range(len(a)) if a[i] != b[i]]


def window_of(m: dict) -> tuple[float, float]:
    """The time span in which the effect of a marker is looked for."""
    if m.get("ts_end"):
        return m["ts"] - SLACK_START, m["ts_end"] + SLACK_END
    return m["ts"] - PRE, m["ts"] + POST


def group_key(m: dict, rules: dict[str, dict[str, Any]]) -> str:
    """Markers of the same action are analysed together. Presets by kind; 'by_note' kinds (options) per typed name;
    free actions by their label."""
    if m["kind"] == "custom":
        return "custom:" + m["label"].strip().lower()
    if rules.get(m["kind"], {}).get("by_note") and m.get("note"):
        return m["kind"] + ":" + m["note"].strip().lower()
    return m["kind"]


def _quiet_windows(markers: list[dict], lo: float, hi: float) -> list[tuple[float, float]]:
    busy = sorted((window_of(m)[0] - 3.0, window_of(m)[1] + 3.0) for m in markers)
    out, t = [], lo
    while t + NOISE_WINDOW <= hi:
        if all(t + NOISE_WINDOW <= b0 or t >= b1 for b0, b1 in busy):
            out.append((t, t + NOISE_WINDOW))
        t += NOISE_WINDOW
    if len(out) > MAX_BASELINE:                                   # spread evenly instead of taking only the start
        step = len(out) / MAX_BASELINE
        out = [out[int(i * step)] for i in range(MAX_BASELINE)]
    return out


def _noise(series: Series, windows: list[tuple[float, float]]):
    """Per (ds, cmd, pos): share of quiet windows in which the byte changed. Per (ds, cmd): payloads seen and how varied they are."""
    changed: Counter = Counter()
    tiles: Counter = Counter()
    seen: dict[tuple[int, int], set[bytes]] = defaultdict(set)
    total: Counter = Counter()
    for a, b in windows:
        for key, ser in series.items():
            s0, s1 = _state_at(ser, a), _state_at(ser, b)
            if s0 is not None and s1 is not None:
                tiles[key] += 1
                for pos in _changed(s0, s1):
                    changed[(*key, pos)] += 1
            i, j = bisect_right(ser[0], a), bisect_right(ser[0], b)
            for d in ser[1][i:j]:
                seen[key].add(d); total[key] += 1
    variety = {k: len(seen[k]) / total[k] for k in total}
    return changed, tiles, seen, variety


def _bits(a: int, b: int) -> list[str]:
    return [f"bit {i}: {(a >> i) & 1}→{(b >> i) & 1}" for i in range(8) if ((a ^ b) >> i) & 1]


def analyze(markers: list[dict], series: Series, rules: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Candidates per action group. See the module docstring. `rules` = catalogue.event_rules()."""
    rules = rules or {}
    done = [m for m in markers]
    if not done:
        return {"baseline": 0, "groups": [], "frames": sum(len(v[0]) for v in series.values())}
    lo = min((t[0][0] for t in series.values() if t[0]), default=min(window_of(m)[0] for m in done))
    hi = max((t[0][-1] for t in series.values() if t[0]), default=max(window_of(m)[1] for m in done))
    windows = _quiet_windows(done, lo, hi)
    changed, tiles, seen, variety = _noise(series, windows)
    n_base = len(windows)

    def noise_rate(key: tuple[int, int], pos: int, length: float) -> float | None:
        if n_base < MIN_BASELINE or tiles[key] < MIN_BASELINE:
            return None
        p = min(0.999, changed[(*key, pos)] / tiles[key])
        return round(1 - (1 - p) ** max(1.0, length / NOISE_WINDOW), 3)         # longer windows collect more noise

    groups: dict[str, dict[str, Any]] = {}
    for m in sorted(done, key=lambda x: x["ts"]):
        g = groups.setdefault(group_key(m, rules), {"key": group_key(m, rules), "kind": m["kind"], "label": m["label"], "n": 0,
                                                    "state": defaultdict(list), "events": defaultdict(int), "length": 0.0,
                                                    "pair": rules.get(m["kind"], {}).get("pair"), "note": m.get("note")})
        a, b = window_of(m)
        g["n"] += 1
        g["length"] = max(g["length"], b - a)
        if g["kind"] in rules and rules[g["kind"]].get("by_note") and m.get("note"):
            g["label"] = f"{m['label'].split(':')[0]}: {m['note']}"
        for key, ser in series.items():
            before, after = _state_at(ser, a), _state_at(ser, b)
            for pos in _changed(before, after):
                if pos >= 0:
                    g["state"][(*key, pos)].append((before[pos], after[pos]))
                else:
                    g["state"][(*key, -1)].append((len(before), len(after)))
            if variety.get(key, 0.0) <= 0.3 and n_base >= MIN_BASELINE:
                i, j = bisect_right(ser[0], a), bisect_right(ser[0], b)
                for d in set(ser[1][i:j]) - seen[key]:
                    g["events"][(*key, d)] += 1

    out = []
    for g in groups.values():
        cands = []
        for (ds, cmd, pos), trans in g["state"].items():
            hits = len(trans)
            (frm, to), top = Counter(trans).most_common(1)[0]
            noise = noise_rate((ds, cmd), pos, g["length"])
            share = top / hits
            score = round((hits / g["n"]) * (1 - (0.5 if noise is None else noise)) * (0.5 + 0.5 * share), 3)
            cands.append({"ds": ds, "cmd": cmd, "pos": pos, "hits": hits, "n": g["n"], "from": frm, "to": to, "share": round(share, 2),
                          "noise": noise, "score": score, "bits": _bits(frm, to) if pos >= 0 and hits else [], "status": "unknown"})
        cands.sort(key=lambda c: (-c["score"], -c["hits"], c["ds"], c["cmd"], c["pos"]))
        events = [{"ds": ds, "cmd": cmd, "data": d.hex(), "hits": h, "n": g["n"]} for (ds, cmd, d), h in g["events"].items() if h >= 2]
        events.sort(key=lambda e: (-e["hits"], e["ds"], e["cmd"]))
        out.append({"key": g["key"], "kind": g["kind"], "label": g["label"], "n": g["n"], "pair": g["pair"], "note": g["note"],
                    "candidates": cands[:12], "events": events[:8], "_all": cands})
    by_key = {g["key"]: g for g in out}

    def partner(g):                                   # the group of the opposite action (same typed name for option_on/off)
        if not g["pair"]:
            return None
        k = g["pair"] + (":" + g["key"].split(":", 1)[1] if ":" in g["key"] else "")
        return by_key.get(k)

    for g in out:
        p = partner(g)
        for c in g["_all"]:
            full = c["hits"] == c["n"] and c["n"] >= 2
            noise_ok = c["noise"] is not None
            if full and noise_ok and c["noise"] <= MAX_NOISE["assumed"] and c["pos"] >= 0:
                c["status"] = "assumed"
            if not (c["status"] == "assumed" and c["share"] == 1.0 and c["noise"] <= MAX_NOISE["confirmed"]):
                continue
            if p:                                      # the opposite action must flip the same byte back
                back = next((x for x in p["_all"] if (x["ds"], x["cmd"], x["pos"]) == (c["ds"], c["cmd"], c["pos"])), None)
                if back and back["hits"] == back["n"] >= 2 and back["share"] == 1.0 and (back["from"], back["to"]) == (c["to"], c["from"]):
                    c["status"] = "confirmed"; c["paired"] = True
            elif not g["pair"] and c["n"] >= 5 and c["noise"] <= MAX_NOISE["unpaired"]:
                c["status"] = "confirmed"
    for g in out:
        g["candidates"] = [c for c in g.pop("_all") if c in g["candidates"]]
        g["best"] = g["candidates"][0] if g["candidates"] else None
    out.sort(key=lambda g: (g["kind"], g["key"]))
    return {"baseline": n_base, "groups": out, "frames": sum(len(v[0]) for v in series.values())}


def run(store, name: str, rules: dict[str, dict[str, Any]] | None = None, markers: list[dict] | None = None) -> dict[str, Any]:
    """Load markers and frames for one source and analyse them."""
    markers = store.markers(name) if markers is None else markers
    markers = [m for m in markers if not (m.get("step_group") and not m.get("ts_end"))]    # a guided step that was never finished
    if not markers:
        return analyze([], {}, rules)
    lo = min(window_of(m)[0] for m in markers) - 1800
    hi = max(window_of(m)[1] for m in markers) + 1800
    res = analyze(markers, store.frame_series(name, lo, hi), rules)
    res["markers"] = len(markers)
    return res


def activity(store, name: str, since: float, until: float, rules: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Live hint during a guided step: how many bytes changed in [since, until] that normally stay quiet?"""
    series = store.frame_series(name, since - 3600, until + 1)
    fake = [{"ts": since + SLACK_START, "ts_end": until - SLACK_END, "kind": "probe", "label": "probe", "note": None}]
    res = analyze(fake, series, rules)
    g = res["groups"][0] if res["groups"] else None
    quiet = [c for c in (g["candidates"] if g else []) if c["noise"] is not None and c["noise"] <= 0.25]
    return {"changes": len(quiet), "baseline": res["baseline"], "best": quiet[0] if quiet else None}
