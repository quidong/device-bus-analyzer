"""Recorded actions (markers) and the Learned page: analysis (noise, repeats, pairs). The companion UI that recorded them is gone;
the data and the Learned page stay for existing installations."""
import base64
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
    assert not [c for c in g["door_open"]["candidates"] if c["pos"] == 0]                    # a counter changes on its own: never even a candidate


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


def test_every_key_used_by_the_device_and_mcp_pages_exists_in_all_languages():
    files = __import__("importlib.resources", fromlist=["files"]).files("device_bus_analyzer")
    for name in ("devices.html", "mcp.html", "help.html", "_srcnav.html", "learn.html"):
        root = open(str(files.joinpath("templates/" + name)), encoding="utf-8").read()
        for k in set(re.findall(r"\bt\.(\w+)", root)) - {"format"}:
            for lang in i18n.LANGS:
                assert k in i18n.STR[lang], (name, k, lang)


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


def test_companion_is_gone(client):
    login(client)
    assert client.get("/s/dw/companion").status_code == 404
    assert client.get("/static/companion.js").status_code == 404
    html = client.get("/s/dw/runs").text
    assert "/companion" not in html and "companion.js" not in html


def test_markers_can_no_longer_be_written_but_stay_readable(client, store):
    token = login(client)
    n = len(store.markers("dw"))
    assert client.post("/s/dw/markers", data={"csrf": token, "kind": "door_open"}).status_code in (404, 405)
    assert client.post("/s/dw/markers/1/end", data={"csrf": token}).status_code in (404, 405)
    assert client.post("/s/dw/markers/1/delete", data={"csrf": token}).status_code in (404, 405)
    assert client.get("/s/dw/activity?since=1").status_code == 404
    assert len(store.markers("dw")) == n == 6                                                   # nothing was lost


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


def test_device_card_opens_the_device_and_uses_icon_buttons(client, store):
    login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", "h.lan", 6053, base64.b64encode(bytes(32)).decode())
    html = client.get("/devices?lang=de").text
    card = html[html.index('<article class="dev">'):html.index("</article>")]
    assert 'class="devlink" href="/s/dw"' in card and 'class="tile"' in card.split("</a>")[0] and ">dw<" in card.split("</a>")[0]
    assert "/companion" not in card and "details" not in card and "&#8943;" not in card                   # no "..." menu any more
    bar = card[card.index('class="actions iconbar"'):]
    buttons = re.findall(r'<(?:a|button)\b[^>]*class="ibtn[^"]*"[^>]*>', bar)
    assert len(buttons) == 5 and all('aria-label="' in b and 'title="' in b for b in buttons)          # frames, firmware, pause, edit, delete
    assert 'title="Bearbeiten"' in bar and 'title="Löschen"' in bar and 'title="Pausieren"' in bar
    assert "<svg" in bar and ">Bearbeiten<" not in bar                                                   # symbols, not words
    assert client.get("/s/dw").headers["location"] == "/s/dw/runs"
    assert client.get("/s/nope").status_code == 404


def test_unfinished_guided_steps_are_ignored(store):
    put_frames(store, "dw", series(door))
    for m in door_markers():
        store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
    store.add_marker("dw", "door_open", "Door opened", ts=T0 + 300, step_group="g")             # started, never finished
    res = analysis.run(store, "dw", RULES)
    assert {g["kind"]: g["n"] for g in res["groups"]} == {"door_open": 3, "door_close": 3} and res["markers"] == 6


def test_protocol_knowledge_keeps_the_device_navigation(client, store):
    login(client)
    html = client.get("/s/dw/spec?lang=en").text
    assert 'href="/s/dw/learn"' in html and "/companion" not in html and "dw · bshdbus" in html       # still inside the device
    assert 'href="/s/dw/spec"' in client.get("/s/dw/learn").text and "/findings/" not in client.get("/s/dw/learn").text
    assert client.get("/s/nope/spec").status_code == 404
    store.source("fresh", "bshdbus")                                                              # nothing recorded with the companion
    assert 'href="/s/fresh/learn"' not in client.get("/s/fresh/runs").text

def test_no_page_shows_a_python_method_instead_of_a_text(client, store):
    """t.copy / t.values would be the dict methods in Jinja; texts with such names must be looked up as t['copy']."""
    login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", "h.lan", 6053, None)
    for path in ("/devices", "/mcp", "/help", "/firmware/bshdbus", "/s/dw/homeassistant", "/s/dw/commands?ds=17&cmd=1010", "/s/dw/learn"):
        html = client.get(path, params={"lang": "de"}).text
        assert "built-in method" not in html and "<bound method" not in html, path
    files = __import__("importlib.resources", fromlist=["files"]).files("device_bus_analyzer").joinpath("templates")
    for f in files.iterdir():
        if f.name.endswith(".html"):
            assert not re.search(r"\bt\.(copy|values|items|keys|get|pop|update|clear)\b", f.read_text(encoding="utf-8")), f.name


def test_analysed_share_counts_telegram_types_not_telegrams(client, store):
    """A heartbeat sent every minute must not dominate: one known type with 500 telegrams and three unknown types with one
    telegram each are 1 of 4 types = 25 %, not 500 of 503 telegrams = 99 %."""
    login(client)
    store.source("hb", "bshdbus")
    store.save_device("hb", "bshdbus", "dishwasher", "Neff", "S413K60S0E", "h.lan", 6053, None)
    sid = store.source_by_name("hb")["id"]
    rows = [(sid, T0 + i, 0x17, 0x1010, b"\x00\x01") for i in range(500)]                 # known in the spec (confirmed)
    rows += [(sid, T0 + 600 + i, 0x17, 0x7770 + i, b"\x00") for i in range(3)]             # three unknown types, once each
    store.db.executemany("INSERT INTO frames(source_id, ts, ds, cmd, data, crc_ok) VALUES(?,?,?,?,?,1)", rows); store.db.commit()
    html = client.get("/devices?lang=de").text
    card = html[html.index('class="devlink" href="/s/hb"'):]
    card = card[:card.index("</article>")]
    assert "<b>25 %</b>" in card
    # two colours: confirmed part and, behind it, the assumed rest (here all of the 25 % is confirmed)
    assert '<rect class="c" x="0" y="0" width="25"' in card and '<rect class="a" x="25" y="0" width="0"' in card and "25 % bestätigt" in card
    assert "angenommen" not in card.split('class="an-legend"')[1]                       # no empty "0 % assumed" entry
    assert 'style="' not in card                                                         # the CSP forbids inline styles
    assert "1 von 4 Telegrammarten" in card and "(1 bestätigt)" in card


def test_analysed_share_splits_confirmed_and_assumed(client, store):
    login(client)
    store.source("hb2", "bshdbus")
    store.save_device("hb2", "bshdbus", "dishwasher", "Neff", "S413K60S0E", "h.lan", 6053, None)
    sid = store.source_by_name("hb2")["id"]
    rows = [(sid, T0, 0x17, 0x1010, b"\x00\x01"),            # confirmed
            (sid, T0 + 1, 0x17, 0x1013, b"\x01"),             # confirmed
            (sid, T0 + 2, 0x25, 0x2011, b"\xa5"),             # assumed
            (sid, T0 + 3, 0x25, 0x2015, b"\x0f\xff")]        # unknown
    store.db.executemany("INSERT INTO frames(source_id, ts, ds, cmd, data, crc_ok) VALUES(?,?,?,?,?,1)", rows); store.db.commit()
    html = client.get("/devices?lang=de").text
    card = html[html.index('class="devlink" href="/s/hb2"'):]
    card = card[:card.index("</article>")]
    assert "<b>75 %</b>" in card and "3 von 4 Telegrammarten" in card
    assert '<rect class="c" x="0" y="0" width="50"' in card and '<rect class="a" x="50" y="0" width="25"' in card
    assert "50 % bestätigt" in card and "25 % angenommen" in card
