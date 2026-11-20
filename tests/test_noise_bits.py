"""Noise per bit, the hands-off baseline, bit masks in what is learned, and the guided timers (hold / rest)."""
import sqlite3

import pytest
from test_companion import MAIL, PW, T0, login, mk

from device_bus_analyzer import analysis, catalog, learned
from device_bus_analyzer.config import Settings
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
        assert [s["hold"] for s in door["steps"]] == [12, 12]
    prog = next(g for g in catalog.controls("dishwasher")["guided"] if g["id"] == "program")
    assert [s["hold"] for s in prog["steps"]] == [0]                                                        # typing steps need no timer


def test_validation_rejects_bad_timers(monkeypatch):
    cat = catalog._base()
    bad = {**cat, "controls": {**cat["controls"], "x": {"events": [], "guided": [{"id": "g", "de": "a", "en": "a", "es": "a", "fr": "a", "it": "a", "rest": -1,
                                                                                    "steps": []}]}}}
    monkeypatch.setattr(catalog, "_base", lambda: bad)
    assert any("rest/hold" in p or "incomplete" in p for p in catalog.validate_catalog())


def test_rest_marker_is_accepted_by_the_server(tmp_path):
    from fastapi.testclient import TestClient

    from device_bus_analyzer.web import create_app
    store = Store(tmp_path / "t.sqlite")
    store.source("dw", "bshdbus")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="t" * 20), store), follow_redirects=False)
    csrf = login(c)
    r = c.post("/s/dw/markers", data={"csrf": csrf, "kind": "rest", "step_group": "g1"})
    assert r.status_code == 200 and r.json()["kind"] == "rest"
    assert c.post("/s/dw/markers", data={"csrf": csrf, "kind": "nonsense"}).status_code == 422


@pytest.mark.parametrize("fast", [True])
def test_guided_timers_in_the_real_browser(tmp_path, fast):
    import shutil
    import socket
    import threading
    import time

    import uvicorn
    pw = pytest.importorskip("playwright.sync_api")
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        pytest.skip("no Chrome/Chromium available")
    from device_bus_analyzer.web import create_app
    store = Store(tmp_path / "ui.sqlite")
    store.source("dw", "bshdbus")
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", None)
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = uvicorn.Server(uvicorn.Config(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456"), store),
                                        host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
            pg = b.new_page(viewport={"width": 390, "height": 800}); errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            base = f"http://127.0.0.1:{port}"
            pg.goto(base + "/login?lang=en"); pg.fill("input[name=email]", MAIL); pg.fill("input[name=password]", PW); pg.click("button")
            pg.goto(base + "/s/dw/companion?lang=en&fast=1")
            pg.click("#cp-scripts button:has-text('Open and close the door')")
            assert pg.is_visible("#cp-go") and not pg.is_visible("#cp-text")                                # first screen: only "Go"
            pg.click("#cp-go")
            pg.wait_for_selector("#cp-text:has-text('Hands off')")                                          # rest phase with a countdown, no Done button
            assert not pg.is_visible("#cp-done") and pg.is_visible("#cp-wait")
            assert "Guided check" in pg.inner_text("#cp-check") and "Open and close the door" in pg.inner_text("#cp-check")
            pg.wait_for_selector("#cp-progress:has-text('Step 1 of 6')")                                    # rest is over: the action comes first, no timer
            assert pg.is_visible("#cp-done") and not pg.is_visible("#cp-wait") and "Open the door" in pg.inner_text("#cp-text")
            assert "Nothing unusual" in pg.inner_text("#cp-hint")                                           # hint says "nothing so far" at once
            pg.click("#cp-done")
            pg.wait_for_selector("#cp-text:has-text('Wait')")                                               # after the action: labelled waiting + progress bar
            assert pg.is_visible("#cp-wait") and pg.is_visible("#cp-timer .bar") and not pg.is_visible("#cp-done")
            pg.wait_for_selector("#cp-progress:has-text('Step 2 of 6')")
            assert pg.is_visible("#cp-done") and not pg.is_visible("#cp-wait")
            kinds = [(m["kind"], bool(m["ts_end"])) for m in store.markers("dw")]
            assert kinds[0] == ("rest", True) and kinds[1] == ("door_open", True) and kinds[2] == ("door_close", False)
            n = len(store.markers("dw")); pg.click("#cp-abort")                                              # abort leaves no open step behind
            pg.wait_for_selector("#cp-main:visible")
            assert len(store.markers("dw")) == n - 1 and errors == []
    finally:
        srv.should_exit = True; th.join(5); store.close()
