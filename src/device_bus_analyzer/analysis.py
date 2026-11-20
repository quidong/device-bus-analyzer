"""Companion analysis: which bytes change when the person does something at the appliance?

Input: the markers (what was done, when, timed by the server) and the stored frames. Nothing is sent anywhere.

For every marker the state of each (dest, command) payload just before is compared with the state just after. Bytes that change
become candidates. Three safeguards keep it honest:

* **Noise model.** Counters, timers and sensor values change on their own. The same comparison is run on quiet windows
  (no marker nearby, preferably the "rest" phase of a guided check, i.e. the same appliance state); a byte that changes in
  many of those is penalised and can never be confirmed. The noise is judged **per bit**: a status byte whose bit 1 flickers
  by itself but whose bit 6 stays quiet is compared on the quiet bits only (``mask`` in the candidate).
* **Repeats.** A candidate only counts when it shows up again and again for the same action (hits / n).
* **Pairs.** Door open / door closed (and other opposite actions) must flip the same byte back and forth. Only then is a
  candidate 'confirmed'; consistent repeats alone give 'assumed'.

Everything here is a pure function of its inputs, so it is easy to test with synthetic frames.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from typing import Any

PRE = 3.0          # seconds before an instant marker that may already belong to the action (pressed, then tapped)
POST = 6.0         # seconds after an instant marker in which the bus reacts
SLACK_START = 1.0  # same for actions with a duration (start / end tap)
SLACK_END = 2.0
NOISE_WINDOW = PRE + POST
MIN_BASELINE = 5   # fewer quiet windows than this: the noise is unknown and nothing is confirmed
MAX_BASELINE = 300
NOISY_BIT = 0.2    # a bit that flips in more than this share of quiet windows is ignored when comparing
RATE_NEAR = 240.0   # seconds around the actions in which the change rate of rare telegrams is measured
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


def _silent(m: dict, series: Series) -> bool:
    """No frame at all around the action (the appliance was off or not connected): nothing could have been seen."""
    a, b = window_of(m)
    return not any(bisect_right(t, b + POST) - bisect_left(t, a - PRE) for t, _ in series.values())


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


def _rates(series: Series, marks: list[dict]) -> dict[tuple, float]:
    """Changes per second of every byte (ds, cmd, pos) and bit (ds, cmd, pos, bit) while NO action was going on. Telegrams that are rare
    (a clock every minute, a counter) cannot show their change inside a short quiet window, but their rate still tells how likely they
    are to change by chance during an action. Gaps (appliance off) and the action windows themselves are left out."""
    spans = sorted(window_of(m) for m in marks)
    starts, ends = [], []
    for a, b in spans:
        a, b = a - 3.0, b + 3.0
        if ends and a <= ends[-1]:
            ends[-1] = max(ends[-1], b)
        else:
            starts.append(a); ends.append(b)

    def busy(t: float) -> bool:
        i = bisect_right(starts, t) - 1
        return i >= 0 and t <= ends[i]

    def near(t: float) -> bool:                                       # the same appliance state: a few minutes around the actions only
        i = bisect_right(starts, t) - 1
        return (i >= 0 and t - ends[i] <= RATE_NEAR) or (i + 1 < len(starts) and starts[i + 1] - t <= RATE_NEAR)

    out: dict[tuple, float] = {}
    for key, (ts, data) in series.items():
        if len(ts) < 6:
            continue
        gaps = sorted(ts[i] - ts[i - 1] for i in range(1, len(ts)))
        med = gaps[len(gaps) // 2]
        if med <= 0:
            continue
        T, n = 0.0, 0
        ch: Counter = Counter()
        for i in range(1, len(ts)):
            dt = ts[i] - ts[i - 1]
            if dt <= 0 or dt > 5 * med or busy(ts[i]) or busy(ts[i - 1]) or not near(ts[i]):
                continue
            T += dt; n += 1
            x, y = data[i - 1], data[i]
            for pos in range(min(len(x), len(y))):
                if x[pos] != y[pos]:
                    ch[(pos, -1)] += 1
                    for bit in range(8):
                        if ((x[pos] ^ y[pos]) >> bit) & 1:
                            ch[(pos, bit)] += 1
        if n >= 5 and T > 0:
            for (pos, bit), c in ch.items():
                out[(*key, pos) if bit < 0 else (*key, pos, bit)] = c / T
    return out


def _by_rate(rate: float | None, length: float) -> float | None:
    return None if rate is None else round(1 - math.exp(-rate * max(length, NOISE_WINDOW)), 3)


def _noise(series: Series, windows: list[tuple[float, float]]):
    """Per (ds, cmd, pos): share of quiet windows in which the byte changed, the noisy bits and the changes that remain on the quiet
    bits. Per (ds, cmd): payloads seen and how varied they are."""
    diffs: dict[tuple[int, int, int], list[int]] = defaultdict(list)       # xor of the byte before/after, one entry per quiet window
    tiles: Counter = Counter()
    seen: dict[tuple[int, int], set[bytes]] = defaultdict(set)
    total: Counter = Counter()
    for a, b in windows:
        for key, ser in series.items():
            s0, s1 = _state_at(ser, a), _state_at(ser, b)
            if s0 is not None and s1 is not None:
                tiles[key] += 1
                for pos in _changed(s0, s1):
                    diffs[(*key, pos)].append(s0[pos] ^ s1[pos] if pos >= 0 else 0xFF)
            i, j = bisect_right(ser[0], a), bisect_right(ser[0], b)
            for d in ser[1][i:j]:
                seen[key].add(d); total[key] += 1
    noisy: dict[tuple[int, int, int], int] = {}
    changed: Counter = Counter()
    bitchg: Counter = Counter()                                            # (ds, cmd, pos, bit): quiet windows in which this one bit changed
    for k, xs in diffs.items():
        if k[2] >= 0:
            for bit in range(8):
                bitchg[(*k, bit)] = sum(1 for x in xs if (x >> bit) & 1)
        n = tiles[k[:2]]
        mask = 0
        if n >= MIN_BASELINE and k[2] >= 0:
            for bit in range(8):
                if sum(1 for x in xs if (x >> bit) & 1) / n > NOISY_BIT:
                    mask |= 1 << bit
            if bin(mask).count("1") >= 3:                          # several flickering bits: a counter or timer, the slow high bits are noise too
                mask = 0xFF
        noisy[k] = mask
        changed[k] = sum(1 for x in xs if x & ~mask & 0xFF) if k[2] >= 0 else len(xs)
    variety = {k: len(seen[k]) / total[k] for k in total}
    return changed, tiles, seen, variety, noisy, bitchg


def _bits(a: int, b: int) -> list[str]:
    return [f"bit {i}: {(a >> i) & 1}→{(b >> i) & 1}" for i in range(8) if ((a ^ b) >> i) & 1]


def analyze(markers: list[dict], series: Series, rules: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Candidates per action group. See the module docstring. `rules` = catalogue.event_rules()."""
    rules = rules or {}
    rest = [m for m in markers if m.get("kind") == "rest" and m.get("ts_end")]       # "do nothing" phase: noise of the same appliance state
    done = [m for m in markers if m.get("kind") != "rest"]
    if series:                                                        # an action while the appliance was off leaves no trace on the bus: it is not evidence
        quiet_marks = [m for m in done if _silent(m, series)]
        done = [m for m in done if m not in quiet_marks]
    else:
        quiet_marks = []
    silent: dict[str, dict[str, Any]] = {}
    for m in quiet_marks:
        e = silent.setdefault(group_key(m, rules), {"key": group_key(m, rules), "label": m["label"], "n": 0})
        e["n"] += 1
    silent_list = sorted(silent.values(), key=lambda e: e["key"])
    if not done:
        return {"baseline": 0, "groups": [], "silent": silent_list, "frames": sum(len(v[0]) for v in series.values())}
    lo = min((t[0][0] for t in series.values() if t[0]), default=min(window_of(m)[0] for m in done))
    hi = max((t[0][-1] for t in series.values() if t[0]), default=max(window_of(m)[1] for m in done))
    windows = _quiet_windows(done, lo, hi)
    rest_windows = [w for w in windows if any(m["ts"] <= w[0] and w[1] <= m["ts_end"] for m in rest)]
    if len(rest_windows) >= MIN_BASELINE:
        windows = rest_windows                                      # same state as the action: far better than hours of standby
    changed, tiles, seen, variety, noisy, bitchg = _noise(series, windows)
    n_base = len(windows)
    rates = _rates(series, done)

    def noise_rate(key: tuple[int, int], pos: int, length: float) -> float | None:
        if n_base < MIN_BASELINE or tiles[key] < MIN_BASELINE:
            return None
        p = min(0.999, changed[(*key, pos)] / tiles[key])
        quiet = round(1 - (1 - p) ** max(1.0, length / NOISE_WINDOW), 3)        # longer windows collect more noise
        return max(quiet, _by_rate(rates.get((*key, pos)), length) or 0.0)       # rare telegrams (clock, counter) change by themselves too

    def bit_noise(key: tuple[int, int], pos: int, bit: int, length: float) -> float | None:
        if n_base < MIN_BASELINE or tiles[key] < MIN_BASELINE:
            return None
        p = min(0.999, bitchg[(*key, pos, bit)] / tiles[key])
        quiet = round(1 - (1 - p) ** max(1.0, length / NOISE_WINDOW), 3)
        return max(quiet, _by_rate(rates.get((*key, pos, bit)), length) or 0.0)

    groups: dict[str, dict[str, Any]] = {}
    for m in sorted(done, key=lambda x: x["ts"]):
        g = groups.setdefault(group_key(m, rules), {"key": group_key(m, rules), "kind": m["kind"], "label": m["label"], "n": 0,
                                                    "state": defaultdict(list), "bit": defaultdict(list), "events": defaultdict(int), "length": 0.0,
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
                    keep = ~noisy.get((*key, pos), 0) & 0xFF                 # compare the quiet bits only
                    if before[pos] & keep != after[pos] & keep:
                        g["state"][(*key, pos)].append((before[pos] & keep, after[pos] & keep))
                        for bit in range(8):                                  # the same change looked at bit by bit (a byte may carry
                            if (keep >> bit) & 1 and ((before[pos] ^ after[pos]) >> bit) & 1:     # a consistent bit next to a flapping one)
                                g["bit"][(*key, pos, bit)].append(((before[pos] >> bit) & 1, (after[pos] >> bit) & 1))
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
            mask = ~noisy.get((ds, cmd, pos), 0) & 0xFF if pos >= 0 else 0xFF
            cands.append({"ds": ds, "cmd": cmd, "pos": pos, "mask": mask, "hits": hits, "n": g["n"], "from": frm, "to": to, "share": round(share, 2),
                          "noise": noise, "score": score, "bits": _bits(frm, to) if pos >= 0 and hits else [], "status": "unknown"})
        for (ds, cmd, pos, bit), trans in g["bit"].items():
            byte = next((c for c in cands if (c["ds"], c["cmd"], c["pos"]) == (ds, cmd, pos) and c["mask"] != 1 << bit), None)
            if byte and byte["share"] == 1.0 and byte["hits"] == g["n"] and bin(byte["from"] ^ byte["to"]).count("1") == 1:
                continue                                                      # the byte candidate already is this one bit
            hits = len(trans)
            (b0, b1), top = Counter(trans).most_common(1)[0]
            noise = bit_noise((ds, cmd), pos, bit, g["length"])
            share = top / hits
            score = round((hits / g["n"]) * (1 - (0.5 if noise is None else noise)) * (0.5 + 0.5 * share), 3)
            cands.append({"ds": ds, "cmd": cmd, "pos": pos, "mask": 1 << bit, "hits": hits, "n": g["n"], "from": b0 << bit, "to": b1 << bit,
                          "share": round(share, 2), "noise": noise, "score": score, "bits": [f"bit {bit}: {b0}→{b1}"], "status": "unknown"})
        cands.sort(key=lambda c: (-c["score"], -c["hits"], c["ds"], c["cmd"], c["pos"], -c["mask"]))
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
                back = next((x for x in p["_all"] if (x["ds"], x["cmd"], x["pos"], x["mask"]) == (c["ds"], c["cmd"], c["pos"], c["mask"])
                             and (x["from"], x["to"]) == (c["to"], c["from"]) and x["hits"] == x["n"] >= 2 and x["share"] == 1.0), None)
                if back:
                    c["status"] = "confirmed"; c["paired"] = True
            elif not g["pair"] and c["n"] >= 5 and c["noise"] <= MAX_NOISE["unpaired"]:
                c["status"] = "confirmed"
    rank = {"confirmed": 0, "assumed": 1, "unknown": 2}
    for g in out:
        g["candidates"] = sorted(g.pop("_all"), key=lambda c: (rank[c["status"]], -c["score"], -c["hits"], c["ds"], c["cmd"], c["pos"], -c["mask"]))[:12]
        g["best"] = g["candidates"][0] if g["candidates"] else None
    out.sort(key=lambda g: (g["kind"], g["key"]))
    return {"baseline": n_base, "groups": out, "silent": silent_list, "frames": sum(len(v[0]) for v in series.values())}


def run(store, name: str, rules: dict[str, dict[str, Any]] | None = None, markers: list[dict] | None = None) -> dict[str, Any]:
    """Load markers and frames for one source and analyse them."""
    markers = store.markers(name) if markers is None else markers
    markers = [m for m in markers if not (m.get("step_group") and not m.get("ts_end"))]    # a guided step that was never finished
    if not markers:
        return {**analyze([], {}, rules), "value_fields": [], "markers": 0}
    lo = min(window_of(m)[0] for m in markers) - 1800
    hi = max(window_of(m)[1] for m in markers) + 1800
    series = store.frame_series(name, lo, hi)
    res = analyze(markers, series, rules)
    res["markers"] = len(markers)
    res["value_fields"] = value_candidates(markers, series)
    return res


def activity(store, name: str, since: float, until: float, rules: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Live hint during a guided step: how many bytes changed in [since, until] that normally stay quiet?"""
    series = store.frame_series(name, since - 3600, until + 1)
    fake = [{"ts": since + SLACK_START, "ts_end": until - SLACK_END, "kind": "probe", "label": "probe", "note": None}]
    res = analyze(fake, series, rules)
    g = res["groups"][0] if res["groups"] else None
    quiet = [c for c in (g["candidates"] if g else []) if c["noise"] is not None and c["noise"] <= 0.25]
    last = max((t[0][-1] for t in series.values() if t[0]), default=None)
    return {"changes": len(quiet), "baseline": res["baseline"], "best": quiet[0] if quiet else None,
            "silent_s": None if last is None else round(max(0.0, until - last), 1)}


# --- values: numbers that follow what the display shows ---------------------------------------------------
INTERP_UNIT = {"min_total": "min", "hours": "h", "min_part": "min", "number": ""}
INTERP_TOL = {"min_total": 1.0, "hours": 0.0, "min_part": 1.0, "number": 0.5}
FACTORS = (1.0, 0.1)


def parse_display(note: str | None) -> dict[str, float]:
    """Read what the person typed from the display: '1:45' (time), '105 min', '45', '45 °C', '1,5'. Text such as 'Eco' gives {}."""
    import re
    s = (note or "").strip().lower().replace(",", ".")
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?:\s*h)?", s)
    if m:
        h, mm = int(m[1]), int(m[2])
        return {"min_total": float(h * 60 + mm), "hours": float(h), "min_part": float(mm)}
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(min|m|h|std|°c|°|c|%)?", s)
    if not m:
        return {}
    v, unit = float(m[1]), m[2] or ""
    if unit in ("h", "std"):
        return {"hours": v, "min_total": v * 60}
    if unit in ("min", "m"):
        return {"min_total": v, "number": v}
    return {"number": v, "min_total": v} if not unit else {"number": v}


def value_candidates(markers: list[dict], series: Series, min_readings: int = 4, min_distinct: int = 3) -> list[dict[str, Any]]:
    """Which byte or word equals the number the person read from the display, at every reading?

    The readings (marker kind 'display' with a note) are taken at different moments of a run, so the shown value changes. A candidate
    must match every reading with the same interpretation (total minutes, hour part, minute part or plain number) and the readings must
    differ, otherwise a constant byte would match by accident.
    """
    from .learned import decode_value
    reads = []
    for m in markers:
        interp = parse_display(m.get("note")) if m["kind"] == "display" else {}
        if interp:
            reads.append((m.get("ts_end") or m["ts"], interp))
    if len(reads) < min_readings:
        return []
    out = []
    for interp_name, tol in INTERP_TOL.items():
        mine = [(t, i[interp_name]) for t, i in reads if interp_name in i]
        if len(mine) < min_readings or len({v for _, v in mine}) < min_distinct:
            continue
        for key, ser in series.items():
            states = [(_state_at(ser, t + 0.3), v) for t, v in mine]
            if any(s is None for s, _ in states):
                continue
            longest = min(len(s) for s, _ in states)
            for pos in range(longest):
                for enc in ("u8", "u16be", "u16le"):
                    if enc != "u8" and pos + 1 >= longest:
                        continue
                    for factor in FACTORS:
                        if all(abs((decode_value(enc, pos, factor, s) or -1e9) - v) <= tol for s, v in states):
                            distinct = len({v for _, v in mine})
                            out.append({"ds": key[0], "cmd": key[1], "pos": pos, "enc": enc, "factor": factor, "interp": interp_name,
                                        "unit": INTERP_UNIT[interp_name], "hits": len(mine), "n": len(mine), "distinct": distinct,
                                        "status": "confirmed" if len(mine) >= 6 and distinct >= 5 else "assumed"})
    # a wider word that merely contains the same low byte is the less likely reading: keep the narrower encoding first
    out.sort(key=lambda c: (-c["distinct"], c["enc"] != "u8", c["factor"] != 1.0, c["ds"], c["cmd"], c["pos"]))
    return out[:12]
