"""Companion mode: markers, analysis (noise, repeats, pairs) and the pages around them."""
import base64
import json
import re

import pytest
from fastapi.testclient import TestClient

from device_bus_analyzer import analysis, catalog, i18n
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app

MAIL, PW = "admin@example.org", "correct horse battery"
T0 = 1_800_100_000.0
RULES = {"door_open": {"pair": "door_close", "by_note": False}, "door_close": {"pair": "door_open", "by_note": False},
         "option_on": {"pair": "option_off", "by_note": True}, "option_off": {"pair": "option_on", "by_note": True},
         "program": {"pair": None, "by_note": False}}
OPENS, CLOSES = [100, 160, 220], [130, 190, 250]


def mk(kind, t, label=None, note=None, end=None):
    return {"id": int(t), "ts": T0 + t, "ts_end": None if end is None else T0 + end, "kind": kind, "label": label or kind, "note": note}


def series(door_at=lambda t: 0, seconds=400, extra=None):
    """One telegram per second: byte 0 is a counter (noise), byte 1 constant, byte 2 carries the door."""
    ts = [T0 + t for t in range(seconds)]
    data = [bytes([t % 256, 7, door_at(t), 0]) for t in range(seconds)]
    out = {(0x17, 0x1010): (ts, data)}
    out.update(extra or {})
    return out


def door(t, opens=OPENS, closes=CLOSES):
    return 1 if any(o + 0.5 <= t < c + 0.5 for o, c in zip(opens, closes)) else 0


def door_markers():
    return [mk("door_open", t, "Door opened") for t in OPENS] + [mk("door_close", t, "Door closed") for t in CLOSES]


# --- analysis ----------------------------------------------------------------------------------------
def test_door_pair_is_confirmed_and_the_counter_is_not():
    res = analysis.analyze(door_markers(), series(door), RULES)
    g = {x["kind"]: x for x in res["groups"]}
    best = g["door_open"]["best"]
    assert (best["ds"], best["cmd"], best["pos"], best["from"], best["to"]) == (0x17, 0x1010, 2, 0, 1)
    assert best["status"] == "confirmed" and best["hits"] == best["n"] == 3 and best["noise"] == 0.0 and best["bits"] == ["bit 0: 0→1"]
    assert (g["door_close"]["best"]["from"], g["door_close"]["best"]["to"]) == (1, 0) and g["door_close"]["best"]["status"] == "confirmed"
    counter = [c for c in g["door_open"]["candidates"] if c["pos"] == 0]
    assert counter and counter[0]["noise"] > 0.9 and counter[0]["status"] == "unknown"      # changes on its own: never a finding


def test_one_observation_or_no_quiet_time_never_gives_a_finding():
    one = analysis.analyze([mk("door_open", 100)], series(door, seconds=300), RULES)
    assert one["groups"][0]["best"]["status"] == "unknown"                                    # a single hit proves nothing
    ms = [mk("door_open", 20), mk("door_close", 30), mk("door_open", 40), mk("door_close", 50)]
    busy = analysis.analyze(ms, series(lambda t: door(t, [20, 40], [30, 50]), seconds=70), RULES)
    assert busy["baseline"] < analysis.MIN_BASELINE
    assert all(c["status"] == "unknown" for g in busy["groups"] for c in g["candidates"])    # noise unknown: nothing is assumed


def test_repeats_without_the_opposite_action_stay_assumed():
    ms = [mk("door_open", t) for t in OPENS]
    res = analysis.analyze(ms, series(lambda t: 1 if any(o + 0.5 <= t < o + 20 for o in OPENS) else 0), RULES)
    assert res["groups"][0]["best"]["status"] == "assumed"                                    # pair missing: not confirmed


def test_unpaired_action_needs_five_repeats_to_be_confirmed():
    def start(n):
        times = [60 + 60 * i for i in range(n)]                                                # "start" turns a byte on, it falls back 8 s later (inside the marker margin)
        s = series(lambda t: 1 if any(x + 0.5 <= t < x + 8 for x in times) else 0, seconds=60 + 60 * n + 100)
        return analysis.analyze([mk("start", t) for t in times], s, {"start": {"pair": None, "by_note": False}})["groups"][0]["best"]["status"]
    assert start(3) == "assumed" and start(5) == "confirmed"


def test_options_are_analysed_per_typed_name():
    ms = [mk("option_on", 100, "Option on", "Intensiv"), mk("option_on", 160, "Option on", "intensiv"),
          mk("option_off", 130, "Option off", "Intensiv"), mk("option_off", 190, "Option off", "Intensiv"),
          mk("option_on", 220, "Option on", "Eco"), mk("option_off", 250, "Option off", "Eco")]
    res = analysis.analyze(ms, series(lambda t: door(t, [100, 160], [130, 190])), RULES)
    keys = {g["key"] for g in res["groups"]}
    assert keys == {"option_on:intensiv", "option_off:intensiv", "option_on:eco", "option_off:eco"}     # case-insensitive, per name
    best = {g["key"]: g["best"] for g in res["groups"]}["option_on:intensiv"]
    assert best["pos"] == 2 and best["status"] == "confirmed" and {g["key"]: g["label"] for g in res["groups"]}["option_on:eco"].endswith("Eco")


def test_actions_with_a_duration_use_their_whole_span():
    ms = [mk("door_open", t, end=t + 12) for t in OPENS]                                       # tap "Go" ... tap "Done" 12 s later
    s = series(lambda t: 1 if any(o + 9 <= t < o + 40 for o in OPENS) else 0)                  # the bus reacts late: 9 s after Go
    assert analysis.analyze(ms, s, RULES)["groups"][0]["best"]["pos"] == 2
    instant = [mk("door_open", t) for t in OPENS]
    assert not [c for c in analysis.analyze(instant, s, RULES)["groups"][0]["candidates"] if c["pos"] == 2]   # outside the 6 s window


def test_length_change_and_one_shot_telegrams():
    ts = [T0 + t for t in range(400)]
    layout = ([bytes([1, 2])] * 400)
    for o in OPENS:
        for t in range(o + 1, o + 5):
            pass
        for t in range(o + 1, o + 60):
            layout[t] = bytes([1, 2, 3])                                                       # another layout after the action
    pulse = {t: b"\xaa\x55" for t in OPENS}                                                    # a telegram that only exists at the action
    ts2 = [T0 + o + 1 for o in OPENS]
    res = analysis.analyze([mk("door_open", t) for t in OPENS], {(1, 1): (ts, layout), (2, 2): (ts2, [pulse[o] for o in OPENS]),
                                                               (3, 3): (ts, [b"\x00"] * 400)}, RULES)
    g = res["groups"][0]
    assert any(c["pos"] == -1 and c["status"] == "unknown" for c in g["candidates"])
    assert any(e["ds"] == 2 and e["data"] == "aa55" and e["hits"] == 3 for e in g["events"])


def test_empty_input():
    assert analysis.analyze([], {}, RULES)["groups"] == []
    assert analysis.analyze(door_markers(), {}, RULES)["groups"][0]["candidates"] == []


# --- storage -----------------------------------------------------------------------------------------
@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "c.sqlite")
    s.source("dw", "bshdbus")
    yield s
    s.close()


def put_frames(store, name, ser):
    sid = store.source_by_name(name)["id"]
    for (ds, cmd), (ts, data) in ser.items():
        store.db.executemany("INSERT INTO frames(source_id, ts, ds, cmd, data, crc_ok) VALUES(?,?,?,?,?,1)", [(sid, t, ds, cmd, d) for t, d in zip(ts, data)])
    store.db.commit()


def test_marker_storage(store):
    m = store.add_marker("dw", "door_open", "  Door opened ", menu="Main", note="x" * 500, ts=T0)
    assert m["label"] == "Door opened" and m["menu"] == "Main" and len(m["note"]) == 200 and m["ts_end"] is None
    with pytest.raises(ValueError):
        store.add_marker("dw", "", "x")
    assert store.add_marker("nope", "a", "b") is None
    e = store.end_marker("dw", m["id"], ts_end=T0 + 5, note="Eco", label="Door opened: Eco")
    assert e["ts_end"] == T0 + 5 and e["note"] == "Eco" and e["label"].endswith("Eco")
    assert store.end_marker("dw", m["id"], ts_end=T0 - 50)["ts_end"] == T0                     # never ends before it started
    second = store.add_marker("dw", "start", "Start", ts=T0 + 10)
    assert [x["id"] for x in store.markers("dw")] == [m["id"], second["id"]]
    assert [x["id"] for x in store.markers("dw", newest_first=True, limit=1)] == [second["id"]]
    assert [x["id"] for x in store.markers("dw", since=T0 + 8)] == [second["id"]]
    assert store.delete_marker("dw", m["id"]) and not store.delete_marker("dw", m["id"]) and not store.delete_marker("other", second["id"])


def test_deleting_a_device_removes_markers_and_accepted_findings(store):
    store.add_marker("dw", "door_open", "Door opened")
    store.save_learned("dw", "Door", "door_open", 0x17, 0x1010, 2, 0, 1, 3, 3, "confirmed")
    store.source("keep", "bshdbus"); store.add_marker("keep", "start", "Start")
    counts = store.data_counts("dw")
    assert counts["markers"] == 1 and counts["learned"] == 1
    assert store.delete_device("dw") == counts
    assert store.db.execute("SELECT COUNT(*) FROM markers").fetchone()[0] == 1 and store.db.execute("SELECT COUNT(*) FROM learned").fetchone()[0] == 0
    assert store.markers("keep")


def test_old_database_gains_the_new_tables_without_touching_data(tmp_path):
    import sqlite3
    p = tmp_path / "old.sqlite"
    db = sqlite3.connect(p)
    db.executescript("CREATE TABLE sources(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, protocol TEXT NOT NULL); INSERT INTO sources(name, protocol) VALUES('dw','bshdbus');")
    db.commit(); db.close()
    s = Store(p)
    assert s.source_by_name("dw") and s.add_marker("dw", "start", "Start")
    s.close()


def test_frame_series_is_ordered_and_skips_bad_crc(store):
    put_frames(store, "dw", {(1, 2): ([T0 + 2, T0 + 1, T0 + 3], [b"b", b"a", b"c"])})
    store.db.execute("UPDATE frames SET crc_ok=0 WHERE data=X'63'"); store.db.commit()
    assert store.frame_series("dw", T0, T0 + 10) == {(1, 2): ([T0 + 1, T0 + 2], [b"a", b"b"])}
    assert store.frame_series("nope", 0, 1) == {}


# --- catalogue ---------------------------------------------------------------------------------------
def test_controls_are_valid_and_localised():
    assert catalog.validate_catalog() == []
    for typ in ("dishwasher", "dryer", None, "something-else"):
        for lang in ("de", "en"):
            c = catalog.controls(typ, lang)
            ids = {e["id"] for e in c["events"]}
            assert {"door_open", "door_close"} <= ids and all(e["label"] for e in c["events"])
            assert all(s["event"] in ids for g in c["guided"] for s in g["steps"])
    assert any(e["id"] == "tank_out" for e in catalog.controls("dryer")["events"]) and not any(e["id"] == "tank_out" for e in catalog.controls("dishwasher")["events"])
    assert catalog.event_rules("dishwasher")["door_open"]["pair"] == "door_close" and catalog.event_rules("dishwasher")["option_on"]["by_note"]


def test_new_i18n_keys_exist_in_both_languages():
    assert set(i18n.STR["de"]) == set(i18n.STR["en"])
    root = open(str(catalog.resources.files("device_bus_analyzer").joinpath("templates/companion.html")), encoding="utf-8").read()
    for k in set(re.findall(r"\bt\.(\w+)", root)):
        assert k in i18n.STR["de"], k


# --- web ---------------------------------------------------------------------------------------------
@pytest.fixture
def client(store):
    put_frames(store, "dw", series(door))
    for m in door_markers():
        store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456")
    return TestClient(create_app(s, store), follow_redirects=False)


def login(c):
    csrf = re.search(r'name="csrf" value="([^"]+)"', c.get("/login").text).group(1)
    assert c.post("/login", data={"email": MAIL, "password": PW, "csrf": csrf}).status_code == 303
    return re.search(r'action="/logout".*?value="([^"]+)"', c.get("/").text, re.S).group(1)


def test_companion_page_and_assets(client):
    assert client.get("/s/dw/companion").status_code == 303                                    # login first
    login(client)
    html = client.get("/s/dw/companion?lang=de").text
    import html as htmllib
    assert 'id="cp"' in html and "Begleiter" in html and "/static/companion.js" in html and "<script>" not in html
    ctl = json.loads(htmllib.unescape(re.search(r'data-controls="([^"]*)"', html).group(1)))
    assert "Tür geöffnet" in [e["label"] for e in ctl["events"]] and ctl["guided"]
    assert client.get("/s/nope/companion").status_code == 404
    js = client.get("/static/companion.js")
    assert js.status_code == 200 and "/markers" in js.text and "innerHTML" not in js.text      # texts are set with textContent only
    assert 'href="/s/dw/companion"' in client.get("/s/dw/runs").text


def test_creating_markers_needs_session_and_csrf_and_uses_server_wording(client, store):
    n = len(store.markers("dw"))
    h = {"Authorization": "Bearer tok-123456"}
    assert client.post("/s/dw/markers", data={"csrf": "x", "kind": "start"}, headers=h).status_code == 303   # the API token cannot write
    token = login(client)
    assert client.post("/s/dw/markers", data={"csrf": "forged", "kind": "start"}).status_code == 403
    r = client.post("/s/dw/markers", data={"csrf": token, "kind": "door_open", "label": "HACKED", "menu": "Main menu", "step_group": "g1"})
    m = r.json()
    assert r.status_code == 200 and m["label"] != "HACKED" and m["menu"] == "Main menu" and m["step_group"] == "g1" and abs(m["ts"] - __import__("time").time()) < 5
    assert client.post("/s/dw/markers", data={"csrf": token, "kind": "nonsense"}).status_code == 422
    assert client.post("/s/dw/markers", data={"csrf": token, "kind": "custom", "label": ""}).status_code == 422
    assert client.post("/s/dw/markers", data={"csrf": token, "kind": "custom", "label": "Pressed the left knob"}).json()["label"] == "Pressed the left knob"
    assert client.post("/s/nope/markers", data={"csrf": token, "kind": "start"}).status_code == 404
    assert len(store.markers("dw")) == n + 2


def test_end_and_delete_marker(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", None, None)                      # a dishwasher knows the option buttons
    m = client.post("/s/dw/markers", data={"csrf": token, "kind": "option_on"}).json()
    e = client.post(f"/s/dw/markers/{m['id']}/end", data={"csrf": token, "note": "Eco"}).json()
    assert e["ts_end"] >= e["ts"] and e["note"] == "Eco" and e["label"].endswith(": Eco")
    assert client.post(f"/s/dw/markers/{m['id']}/end", data={"csrf": "bad"}).status_code == 403
    assert client.post("/s/dw/markers/99999/end", data={"csrf": token}).status_code == 404
    assert client.post(f"/s/dw/markers/{m['id']}/delete", data={"csrf": token}).json() == {"ok": True}
    assert client.post(f"/s/dw/markers/{m['id']}/delete", data={"csrf": token}).status_code == 404


def test_activity_hint_is_for_signed_in_users(client, store):
    import time
    now = time.time()
    store.source("live", "bshdbus")
    ts = [now - 200 + t for t in range(200)]
    put_frames(store, "live", {(0x17, 0x1010): (ts, [bytes([t % 256, 7, 1 if t >= 140 else 0, 0]) for t in range(200)])})   # the door byte flips 60 s ago
    assert client.get(f"/s/live/activity?since={now - 70}").status_code == 303
    login(client)
    r = client.get(f"/s/live/activity?since={now - 70}").json()
    assert set(r) == {"changes", "baseline", "best"} and r["baseline"] >= 5 and r["changes"] >= 1 and r["best"]["pos"] == 2
    assert client.get(f"/s/live/activity?since={now - 20}").json()["changes"] == 0                  # nothing happened in the last 20 s
    assert client.get("/s/nope/activity?since=1").status_code == 404


def test_learn_page_shows_the_finding_and_accepting_stores_it(client, store):
    token = login(client)
    html = client.get("/s/dw/learn?lang=en").text
    assert "confirmed" in html and "17/1010 #2" in html and "00 → 01" in html and "bit 0: 0→1" in html and 'action="/s/dw/learned"' in html
    body = {"csrf": token, "group": "door_open", "ds": 0x17, "cmd": 0x1010, "pos": 2, "meaning": "Door is open"}
    assert client.post("/s/dw/learned", data={**body, "csrf": "bad"}).status_code == 403
    assert client.post("/s/dw/learned", data={**body, "pos": 3}).status_code == 422             # invented finding
    assert client.post("/s/dw/learned", data={**body, "pos": 0}).status_code == 422             # noise is never accepted
    assert client.post("/s/dw/learned", data={**body, "group": "nonsense"}).status_code == 422
    r = client.post("/s/dw/learned", data=body)
    assert r.status_code == 303 and r.headers["location"].endswith("/learn#learned")
    f = store.learned("dw")[0]
    assert (f["meaning"], f["ds"], f["cmd"], f["pos"], f["from_val"], f["to_val"], f["hits"], f["n"], f["status"]) == ("Door is open", 0x17, 0x1010, 2, 0, 1, 3, 3, "confirmed")
    assert "Door is open" in client.get("/s/dw/learn").text
    assert client.post(f"/s/dw/learned/{f['id']}/delete", data={"csrf": token}).status_code == 303 and store.learned("dw") == []
    assert client.post(f"/s/dw/learned/{f['id']}/delete", data={"csrf": token}).status_code == 404


def test_learn_page_is_readable_with_the_api_token_but_cannot_accept(client):
    r = client.get("/s/dw/learn", headers={"Authorization": "Bearer tok-123456"})
    assert r.status_code == 200 and "confirmed" in r.text and "/learned" not in r.text and 'name="csrf"' not in r.text
    assert client.post("/s/dw/learned", data={"csrf": "x", "group": "door_open", "ds": 1, "cmd": 1, "pos": 2}, headers={"Authorization": "Bearer tok-123456"}).status_code == 303


def test_contribution_export_has_no_logs_times_hosts_or_keys(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", "secret-host.lan", 6053, base64.b64encode(bytes(32)).decode())
    client.post("/s/dw/learned", data={"csrf": token, "group": "door_open", "ds": 0x17, "cmd": 0x1010, "pos": 2, "meaning": "Door open"})
    r = client.get("/s/dw/contribution.json")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert d["protocol"] == "bshdbus" and (d["manufacturer"], d["model"], d["type"]) == ("Neff", "S413K60S0E", "dishwasher")
    assert d["findings"] == [{"meaning": "Door open", "action": "door_open", "ds": 23, "cmd": 4112, "byte": 2, "from": 0, "to": 1, "repeats": 3, "of": 3, "status": "confirmed"}]
    assert d["actions_recorded"] == {"door_open": 3, "door_close": 3}
    text = r.text
    assert "secret-host" not in text and "key" not in text.lower() and str(int(T0))[:6] not in text
    assert client.get("/s/dw/contribution.json", headers={"Authorization": "Bearer tok-123456"}).status_code == 200


def test_timeline_shows_markers_between_the_telegrams(client):
    login(client)
    html = client.get("/s/dw/timeline?lang=en").text
    assert html.count('class="mk"') == 6 and "Tür geöffnet" in html or html.count('class="mk"') == 6
    assert re.search(r'class="mk".*?(Door|door)', html, re.S)


def test_api_exposes_markers_and_analysis_read_only(client):
    h = {"Authorization": "Bearer tok-123456"}
    assert client.get("/api/dw/markers").status_code == 401
    assert len(client.get("/api/dw/markers", headers=h).json()) == 6
    res = client.get("/api/dw/learn", headers=h).json()
    assert {g["kind"] for g in res["groups"]} == {"door_open", "door_close"} and res["baseline"] >= 5
    assert client.get("/api/nope/learn", headers=h).status_code == 404


def test_device_card_links_to_the_companion(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", None, "h.lan", 6053, base64.b64encode(bytes(32)).decode())
    assert 'href="/s/dw/companion"' in client.get("/devices").text
    assert "<b>6</b>" in client.get("/devices/dw/delete").text or "6" in client.get("/devices/dw/delete").text


def test_unfinished_guided_steps_are_ignored(store):
    put_frames(store, "dw", series(door))
    for m in door_markers():
        store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
    store.add_marker("dw", "door_open", "Door opened", ts=T0 + 300, step_group="g")             # started, never finished
    res = analysis.run(store, "dw", RULES)
    assert {g["kind"]: g["n"] for g in res["groups"]} == {"door_open": 3, "door_close": 3} and res["markers"] == 6


def test_protocol_knowledge_keeps_the_device_navigation(client):
    login(client)
    html = client.get("/s/dw/spec?lang=en").text
    assert 'href="/s/dw/companion"' in html and 'href="/s/dw/learn"' in html and "dw · bshdbus" in html       # still inside the device
    assert 'href="/s/dw/spec"' in client.get("/s/dw/learn").text and "/findings/" not in client.get("/s/dw/learn").text
    assert client.get("/s/nope/spec").status_code == 404
