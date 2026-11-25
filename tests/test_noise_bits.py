"""Noise per bit, the hands-off baseline, bit masks in what is learned, and the guided timers (hold / rest)."""
import sqlite3

from test_companion import T0, mk

from device_bus_analyzer import analysis, catalog, learned
from device_bus_analyzer.store import Store

RULES = {"door_open": {"pair": "door_close", "by_note": False}, "door_close": {"pair": "door_open", "by_note": False},
         "rest": {"pair": None, "by_note": False}}
# What a real dryer (ds 2a, cmd 2252, byte 6) did around one door cycle: 0x41 closed and settled -> 0x03 while the door is open ->
# 0x43 when it is closed, then bit 1 flaps for about 20 s (0x43 <-> 0x41) before it settles on 0x41 again. Seconds after the close.
AFTER_CLOSE = [0.0, 0.2, 3.8, 9.4, 15.5, 20.3]
SPANS = [(200 + 60 * i, 214 + 60 * i) for i in range(3)]              # door open 14 s, three times
SPEED = [1.0, 0.8, 1.2]                                               # the flapping is not equally fast every time


def dryer_series(spans=SPANS, lag=3.0, extra=None):
    """Status payload '03 01 00 00 00 00 <b6> 00 00'. The bus reports a door move `lag` seconds late."""
    ev = [(0.0, 0x41)]
    for (a, b), sp in zip(spans, SPEED):
        ev.append((a + lag, 0x03))
        for k, off in enumerate(AFTER_CLOSE):
            ev.append((b + lag + off * sp, 0x43 if k % 2 == 0 else 0x41))
    ts = [T0 + t for t, _ in ev]
    data = [bytes([3, 1, 0, 0, 0, 0, v, 0, 0]) for _, v in ev]
    return {(0x2A, 0x2252): (list(extra[0]) + ts, list(extra[1]) + data) if extra else (ts, data)}


def guided_markers(rest=True):
    ms = [mk("rest", 0, end=100)] if rest else []
    for a, b in SPANS:
        ms += [mk("door_open", a, "Door opened", end=b), mk("door_close", b, "Door closed", end=b + 14)]
    return ms


def test_the_door_bit_is_found_although_the_byte_after_closing_is_unstable():
    res = analysis.analyze(guided_markers(), dryer_series(), RULES)
    g = {x["kind"]: x for x in res["groups"]}
    assert "rest" not in g
    # as a whole byte the "closed" state is 0x41 or 0x43 depending on when the window ends: no consistent byte transition ...
    byte_close = [c for c in g["door_close"]["candidates"] if c["pos"] == 6 and c["mask"] == 0xFF]
    assert byte_close and byte_close[0]["share"] < 1.0
    # ... but bit 6 flips cleanly every time, in both directions, and that is what gets confirmed
    o, c = g["door_open"]["best"], g["door_close"]["best"]
    assert (o["ds"], o["cmd"], o["pos"], o["mask"], o["bits"], o["status"]) == (0x2A, 0x2252, 6, 0x40, ["bit 6: 1→0"], "confirmed")
    assert (c["pos"], c["mask"], c["bits"], c["status"], c["hits"], c["n"]) == (6, 0x40, ["bit 6: 0→1"], "confirmed", 3, 3)
    assert (c["from"], c["to"]) == (o["to"], o["from"])


def test_the_hands_off_phase_is_the_baseline_when_there_is_enough_of_it():
    res = analysis.analyze(guided_markers(), dryer_series(), RULES)
    assert res["baseline"] == 11                                                                           # 100 s of rest in 9 s windows
    no_rest = analysis.analyze(guided_markers(False), dryer_series(), RULES)
    assert no_rest["baseline"] > res["baseline"]                                                           # without it: every quiet window


def test_noise_that_only_exists_in_another_state_is_not_held_against_the_finding():
    # long before the test the appliance ran a programme and bit 6 of the same byte flapped all the time ...
    pre_ts = [T0 - 1200 + 3 * i for i in range(300)]
    pre = [bytes([3, 1, 0, 0, 0, 0, 0x01 | (0x40 if i % 2 else 0), 0, 0]) for i in range(300)]
    series = dryer_series(extra=(pre_ts, pre))
    with_rest = {g["kind"]: g for g in analysis.analyze(guided_markers(), series, RULES)["groups"]}
    assert with_rest["door_open"]["best"]["status"] == "confirmed" and with_rest["door_open"]["best"]["mask"] == 0x40   # rest phase = same state as the test
    without = {g["kind"]: g for g in analysis.analyze(guided_markers(False), series, RULES)["groups"]}
    assert not [c for c in without["door_open"]["candidates"] if c["pos"] == 6 and c["status"] == "confirmed"]          # that old noise would have hidden the bit


def test_a_counter_byte_is_never_a_candidate():
    ts = [T0 + t for t in range(700)]
    series = {(1, 1): (ts, [bytes([t % 256, 0]) for t in range(700)])}
    series.update(dryer_series(SPANS))
    res = analysis.analyze(guided_markers(), series, RULES)
    assert not [c for g in res["groups"] for c in g["candidates"] if (c["ds"], c["cmd"]) == (1, 1)]


# --- what is learned keeps the mask ---------------------------------------------------------------------------
def test_learned_states_compare_only_the_accepted_bits():
    ov = learned.overlay([{"pos": 6, "to_val": 0x00, "meaning": "Door opened", "ds": 0x2A, "cmd": 0x2252, "mask": 0x40},
                          {"pos": 6, "to_val": 0x40, "meaning": "Door closed", "ds": 0x2A, "cmd": 0x2252, "mask": 0x40}], [])
    d = lambda b6: bytes([3, 1, 0, 0, 0, 0, b6, 0, 0])                                                      # noqa: E731
    assert learned.describe(ov, 0x2A, 0x2252, d(0x03)) == learned.describe(ov, 0x2A, 0x2252, d(0x01)) == ["Door opened"]   # the flapping bit 1 is ignored
    assert learned.describe(ov, 0x2A, 0x2252, d(0x43)) == learned.describe(ov, 0x2A, 0x2252, d(0x41)) == ["Door closed"]
    old = learned.overlay([{"pos": 2, "to_val": 1, "meaning": "Door opened", "ds": 1, "cmd": 2}], [])         # rows without a mask: all bits
    assert learned.describe(old, 1, 2, bytes([0, 0, 1])) == ["Door opened"] and learned.describe(old, 1, 2, bytes([0, 0, 3])) == []


def test_store_adds_the_mask_column_to_an_old_database(tmp_path):
    p = tmp_path / "old.sqlite"
    db = sqlite3.connect(p)
    db.executescript("CREATE TABLE sources(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, protocol TEXT NOT NULL);"
                     "CREATE TABLE learned(id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, meaning TEXT NOT NULL, kind TEXT, ds INTEGER, cmd INTEGER,"
                     " pos INTEGER, from_val INTEGER, to_val INTEGER, hits INTEGER, n INTEGER, status TEXT NOT NULL, created_ts REAL NOT NULL);"
                     "INSERT INTO sources VALUES(1,'dw','macs'); INSERT INTO learned VALUES(1,1,'Door',NULL,1,2,3,0,1,3,3,'confirmed',0);")
    db.commit(); db.close()
    st = Store(p)
    assert st.learned("dw")[0]["mask"] is None                                                              # existing finding: all bits, unchanged
    st.save_learned("dw", "Door open", "door_open", 1, 2, 3, 0x01, 0x00, 3, 3, "confirmed", mask=0x40)
    st.save_learned("dw", "All bits", "x", 1, 2, 4, 0, 1, 3, 3, "confirmed", mask=255)
    got = {f["meaning"]: f["mask"] for f in st.learned("dw")}
    assert got == {"Door": None, "Door open": 0x40, "All bits": None}                                       # 255 is stored as 'all'
    st.close()
    Store(p).close()                                                                                        # reopening is harmless


# --- guided timers --------------------------------------------------------------------------------------------
def test_catalogue_declares_rest_and_hold_for_the_guided_checks():
    assert catalog.validate_catalog() == []
    for dev in ("dishwasher", "dryer", None):
        ctl = catalog.controls(dev)
        assert ctl["guided"] and all(g["rest"] == 90 for g in ctl["guided"])
        door = next(g for g in ctl["guided"] if g["id"] == "door")
        assert [s["hold"] for s in door["steps"]] == [25, 25]
    prog = next(g for g in catalog.controls("dishwasher")["guided"] if g["id"] == "program")
    assert [s["hold"] for s in prog["steps"]] == [0]                                                        # typing steps need no timer


def test_validation_rejects_bad_timers(monkeypatch):
    cat = catalog._base()
    bad = {**cat, "controls": {**cat["controls"], "x": {"events": [], "guided": [{"id": "g", "de": "a", "en": "a", "es": "a", "fr": "a", "it": "a", "rest": -1,
                                                                                    "steps": []}]}}}
    monkeypatch.setattr(catalog, "_base", lambda: bad)
    assert any("rest/hold" in p or "incomplete" in p for p in catalog.validate_catalog())


def test_actions_without_any_bus_traffic_are_not_counted_as_evidence():
    """The appliance was off: those markers must not dilute the hit rate of the ones where it was on."""
    from device_bus_analyzer import analysis
    ts = [1000.0 + 3 * i for i in range(400)]                                         # alive from 1000 to 2200
    vals = [bytes([0, 0x03 if 1300 <= t < 1500 else 0x43]) for t in ts]
    series = {(0x2a, 0x2252): (ts, vals)}
    rules = {"door_open": {"pair": "door_close"}, "door_close": {"pair": "door_open"}}
    mk = lambda kind, t: {"kind": kind, "label": kind, "ts": t, "ts_end": t + 5, "note": None, "menu": ""}      # noqa: E731
    markers = [mk("door_open", 1300), mk("door_close", 1500), mk("door_open", 5000), mk("door_open", 5100), mk("door_close", 5200)]   # 5000+: silent
    res = analysis.analyze(markers, series, rules)
    assert {s["key"]: s["n"] for s in res["silent"]} == {"door_open": 2, "door_close": 1}
    g = next(x for x in res["groups"] if x["key"] == "door_open")
    assert g["n"] == 1                                                                 # only the action with traffic counts
    assert analysis.analyze([mk("door_open", 5000)], series, rules)["groups"] == []


def test_rare_telegrams_that_change_by_themselves_count_as_noise():
    """A clock telegram (one per minute) shows no change inside short quiet windows, yet it lands in actions by chance: its rate outside
    the actions must lower its score, while the door byte that only changes at actions stays clean."""
    from device_bus_analyzer import analysis
    ts_door = [1000.0 + 3 * i for i in range(600)]                                     # status every 3 s, 30 min
    marks, door = [], []
    for k in range(6):
        t = 1100.0 + 250 * k
        marks.append({"kind": "door_open" if k % 2 == 0 else "door_close", "label": "d", "ts": t, "ts_end": t + 5, "note": None, "menu": ""})
    for t in ts_door:
        opened = any(m["ts"] <= t < m["ts"] + 250 and m["kind"] == "door_open" for m in marks)
        door.append(bytes([0, 0x03 if opened else 0x41]))
    ts_clock = [1000.0 + 60 * i for i in range(30)]
    clock = [bytes([0, 0, 0, 0xff - i]) for i in range(30)]                             # changes every frame (a minute counter)
    series = {(0x2a, 0x2252): (ts_door, door), (0x2a, 0x2256): (ts_clock, clock)}
    rules = {"door_open": {"pair": "door_close"}, "door_close": {"pair": "door_open"}}
    res = analysis.analyze(marks, series, rules)
    g = next(x for x in res["groups"] if x["key"] == "door_open")
    clk = [c for c in g["candidates"] if c["cmd"] == 0x2256 and c["pos"] == 3 and c["mask"] == 0xFF]
    door_c = [c for c in g["candidates"] if c["cmd"] == 0x2252 and c["pos"] == 1]
    assert door_c and door_c[0]["noise"] is not None and door_c[0]["noise"] < 0.1
    assert not clk or clk[0]["noise"] is None or clk[0]["noise"] >= 0.1
