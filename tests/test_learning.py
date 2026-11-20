"""Applying what was learned: meaning overlay, values read from the display, device state."""
import re

import pytest
from fastapi.testclient import TestClient
from test_companion import MAIL, PW, T0, door, door_markers, login, put_frames, series  # noqa: F401  (fixtures reused)

from device_bus_analyzer import analysis, learned
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


# --- display parsing ---------------------------------------------------------------------------------
@pytest.mark.parametrize("text,expect", [
    ("1:45", {"min_total": 105.0, "hours": 1.0, "min_part": 45.0}),
    ("0:05 h", {"min_total": 5.0, "hours": 0.0, "min_part": 5.0}),
    ("105", {"number": 105.0, "min_total": 105.0}),
    ("45 min", {"min_total": 45.0, "number": 45.0}),
    ("2 h", {"hours": 2.0, "min_total": 120.0}),
    ("45 °C", {"number": 45.0}),
    ("1,5", {"number": 1.5, "min_total": 1.5}),
    ("Eco", {}), ("", {}), (None, {}), ("12:5", {}),
])
def test_parse_display(text, expect):
    assert analysis.parse_display(text) == expect


# --- decoding ----------------------------------------------------------------------------------------
def test_decode_value_encodings():
    d = bytes([0x01, 0x2C, 0x05])
    assert learned.decode_value("u8", 1, 1.0, d) == 0x2C
    assert learned.decode_value("u16be", 0, 1.0, d) == 0x012C
    assert learned.decode_value("u16le", 0, 1.0, d) == 0x2C01
    assert learned.decode_value("u16be", 0, 0.1, d) == pytest.approx(30.0)
    assert learned.decode_value("u16be", 2, 1.0, d) is None and learned.decode_value("u8", 9, 1.0, d) is None and learned.decode_value("x", 0, 1, d) is None
    assert learned.number(105.0) == "105" and learned.number(30.5) == "30.5"


def test_overlay_maps_values_to_the_meaning_the_person_gave():
    rows = [{"ds": 23, "cmd": 4112, "pos": 2, "from_val": 0, "to_val": 1, "meaning": "Door open"},
            {"ds": 23, "cmd": 4112, "pos": 2, "from_val": 1, "to_val": 0, "meaning": "Door closed"},
            {"ds": 1, "cmd": 1, "pos": -1, "from_val": 2, "to_val": 3, "meaning": "layout"}]
    vals = [{"ds": 37, "cmd": 8200, "pos": 0, "enc": "u8", "factor": 1.0, "meaning": "Remaining", "unit": "min"}]
    ov = learned.overlay(rows, vals)
    assert learned.describe(ov, 23, 4112, bytes([0, 0, 1, 0])) == ["Door open"]
    assert learned.describe(ov, 23, 4112, bytes([0, 0, 0, 0])) == ["Door closed"]
    assert learned.describe(ov, 23, 4112, bytes([0, 0, 7, 0])) == [] and learned.describe(ov, 23, 4112, b"") == []     # unknown value: say nothing
    assert learned.describe(ov, 37, 8200, bytes([105])) == ["Remaining: 105 min"]
    assert learned.describe(ov, 1, 1, b"\x00") == [] and learned.describe({}, 1, 1, b"\x00") == []


# --- values from the display -------------------------------------------------------------------------
def remaining_series(seconds=700):
    """cmd 0x2008: byte 0 = minutes left (u8), bytes 1-2 = hours/minute parts, byte 3 constant, byte 4 a counter."""
    ts, data = [], []
    for t in range(seconds):
        left = 105 - t // 60
        ts.append(T0 + t); data.append(bytes([left, left // 60, left % 60, 9, t % 256]))
    return {(0x25, 0x2008): (ts, data)}


def reading(t, note):
    return {"id": t, "ts": T0 + t, "ts_end": None, "kind": "display", "label": "Display shows", "note": note}


def test_a_byte_that_follows_the_display_is_found():
    ms = [reading(30, "1:45"), reading(130, "1:44"), reading(250, "1:41"), reading(370, "1:39"), reading(490, "1:37")]
    found = analysis.value_candidates(ms, remaining_series())
    best = [c for c in found if (c["interp"], c["pos"], c["enc"]) == ("min_total", 0, "u8")]
    assert best and best[0]["hits"] == 5 and best[0]["unit"] == "min" and best[0]["status"] == "assumed" and best[0]["factor"] == 1.0
    assert any(c["interp"] == "hours" and c["pos"] == 1 for c in found) is False                 # the hour part barely changes: not enough distinct readings
    assert not [c for c in found if c["pos"] == 3 or c["pos"] == 4 and c["interp"] != "number"]  # constant byte and counter never match
    assert found[0]["ds"] == 0x25 and found[0]["cmd"] == 0x2008


def test_hour_and_minute_parts_and_plain_numbers():
    ms = [reading(t, n) for t, n in [(30, "105"), (130, "104"), (250, "101"), (370, "99"), (490, "97"), (610, "95")]]
    found = analysis.value_candidates(ms, remaining_series())
    assert any(c["interp"] == "min_total" and c["pos"] == 0 and c["status"] == "confirmed" for c in found)     # 6 readings, 6 distinct
    ms = [reading(t, n) for t, n in [(30, "1:45"), (130, "1:44"), (250, "1:41"), (370, "1:39")]]
    two = analysis.value_candidates(ms, remaining_series())
    assert any(c["interp"] == "min_part" and c["pos"] == 2 for c in two)


def test_too_few_or_unusable_readings_find_nothing():
    s = remaining_series()
    assert analysis.value_candidates([reading(30, "1:45"), reading(130, "1:44"), reading(250, "1:41")], s) == []        # fewer than 4
    assert analysis.value_candidates([reading(30, "1:45")] * 4, s) == []                                              # same value: nothing to correlate
    assert analysis.value_candidates([reading(t, "Eco") for t in (30, 130, 250, 370)], s) == []                         # not a number
    other = [dict(reading(t, "1:45"), kind="program") for t in (30, 130, 250, 370)]
    assert analysis.value_candidates(other, s) == []
    wrong = [reading(30, "9:59"), reading(130, "0:01"), reading(250, "5:30"), reading(370, "2:20")]
    assert analysis.value_candidates(wrong, s) == []                                                                   # nothing follows these


def test_readings_with_a_duration_use_the_time_the_step_ended():
    ms = [dict(reading(t, n), ts_end=T0 + t + 8) for t, n in [(30, "1:45"), (130, "1:44"), (250, "1:41"), (370, "1:39")]]
    assert any(c["pos"] == 0 and c["interp"] == "min_total" for c in analysis.value_candidates(ms, remaining_series()))


# --- web ---------------------------------------------------------------------------------------------
@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "l.sqlite")
    s.source("dw", "bshdbus")
    yield s
    s.close()


@pytest.fixture
def client(store):
    put_frames(store, "dw", {**series(door), **remaining_series()})
    for m in door_markers():
        store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
    for t, n in [(30, "1:45"), (130, "1:44"), (250, "1:41"), (370, "1:39"), (490, "1:37")]:
        store.add_marker("dw", "display", "Display shows", note=n, ts=T0 + t)
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456")
    return TestClient(create_app(s, store), follow_redirects=False)


def test_learn_page_offers_display_values_and_accepting_applies_them_everywhere(client, store):
    token = login(client)
    html = client.get("/s/dw/learn?lang=en").text
    assert "Values from the display" in html and 'action="/s/dw/values"' in html and "25/2008 #0" in html
    body = {"csrf": token, "ds": 0x25, "cmd": 0x2008, "pos": 0, "enc": "u8", "factor": 1.0, "interp": "min_total", "meaning": "Remaining time", "unit": "min"}
    assert client.post("/s/dw/values", data={**body, "csrf": "bad"}).status_code == 403
    assert client.post("/s/dw/values", data={**body, "pos": 3}).status_code == 422                # invented
    assert client.post("/s/dw/values", data={**body, "enc": "u16be"}).status_code == 422
    assert client.post("/s/dw/values", data=body).status_code == 303
    v = store.learned_values("dw")[0]
    assert (v["meaning"], v["unit"], v["pos"], v["enc"], v["interp"], v["hits"], v["n"]) == ("Remaining time", "min", 0, "u8", "min_total", 5, 5)
    frames = client.get("/s/dw/frames?cmd=2008&lang=en&limit=1000").text
    assert "Remaining time: 105 min" in frames and "Remaining time: 98 min" in frames
    assert "Remaining time: " in client.get("/s/dw/timeline?cmd=2008&lang=en").text
    api = client.get("/api/dw/frames?cmd=2008&limit=3", headers={"Authorization": "Bearer tok-123456"}).json()
    assert api[0]["learned"] == ["Remaining time: 105 min"]
    assert "Remaining time" in client.get("/s/dw/learn").text and 'action="/s/dw/values/%d/delete"' % v["id"] in client.get("/s/dw/learn").text
    assert client.post(f"/s/dw/values/{v['id']}/delete", data={"csrf": token}).status_code == 303 and store.learned_values("dw") == []
    assert client.post(f"/s/dw/values/{v['id']}/delete", data={"csrf": token}).status_code == 404
    assert "Remaining time: 105" not in client.get("/s/dw/frames?cmd=2008&limit=1000").text


def test_accepted_findings_show_their_meaning_in_telegram_lists_and_on_the_device_card(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", None, None)
    for group, meaning in (("door_open", "Door is open"), ("door_close", "Door is closed")):
        assert client.post("/s/dw/learned", data={"csrf": token, "group": group, "ds": 0x17, "cmd": 0x1010, "pos": 2, "meaning": meaning}).status_code == 303
    frames = client.get("/s/dw/frames?cmd=1010&limit=1000&lang=en").text
    assert frames.count("Door is open") > 20 and "Door is closed" in frames
    card = client.get("/devices?lang=en").text
    assert 'class="tag learned">Door is closed' in card or 'class="tag learned">Door is open' in card
    # the card shows the NEWEST telegram: door byte is 0 at the end of the recording
    assert "Door is closed" in card and "Door is open" not in card.split('class="now"')[1].split("</dl>")[0]


def test_deleting_a_device_removes_taught_values(store):
    store.save_learned_value("dw", "Remaining", "min", 1, 2, 0, "u8", 1.0, "min_total", 5, 5, "assumed")
    assert store.data_counts("dw")["learned"] == 1
    store.delete_device("dw")
    assert store.db.execute("SELECT COUNT(*) FROM learned_values").fetchone()[0] == 0
