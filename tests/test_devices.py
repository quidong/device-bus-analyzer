"""Device management: catalogue, additive storage, one-time import of the old environment configuration, web dialog, collectors.

The central promise: configuring devices never loses or changes recorded data, and secrets never leave the server."""
import asyncio
import base64
import re
import sqlite3
import types

import pytest
from conftest import raw1
from fastapi.testclient import TestClient

from device_bus_analyzer import catalog, config
from device_bus_analyzer.collector import CollectorManager
from device_bus_analyzer.config import Device, Settings
from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app

KEY = base64.b64encode(bytes(range(32))).decode()
KEY2 = base64.b64encode(bytes(range(1, 33))).decode()
MAIL, PW = "admin@example.org", "correct horse battery"
TABLES = ("sources", "sessions", "bursts", "frames", "heartbeats", "gaps")


def snapshot(path):
    db = sqlite3.connect(path)
    out = {t: db.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in TABLES}
    db.close()
    return out


def fill(store, name="dw"):
    sid = store.source(name, "bshdbus")
    f = build_frame(0x17, 0x1010, b"\x1c")
    for i in (1, 2, 3):
        store.ingest_line(sid, raw1(i, i * 1000, f), 1_800_000_000.0 + i)
    return sid


# --- catalogue --------------------------------------------------------------------------------
def test_catalog_has_concrete_brands_and_firmware_for_each_protocol():
    assert catalog.validate_catalog() == []
    c = catalog.build([{"type": "washer", "manufacturer": "Acme", "model": "X1", "protocol": "bshdbus"},
                       {"type": "dishwasher", "manufacturer": "Neff", "model": "Own 1", "protocol": "bshdbus"}])
    assert {"dishwasher", "dryer", "washer"} <= set(c["types"])
    mans = {m["name"]: m for m in c["manufacturers"]}
    assert {"Bosch", "Siemens", "Neff", "Electrolux", "AEG"} <= set(mans)            # brands, not families
    assert mans["Electrolux"]["protocol"] == mans["AEG"]["protocol"] == "macs" and mans["Bosch"]["protocol"] == "bshdbus"
    assert mans["Acme"]["models"] == ["X1"] and {"S413K60S0E", "Own 1"} <= set(mans["Neff"]["models"])
    assert sorted(c["protocols"]) == ["bshdbus", "macs"]
    for proto in c["protocols"]:
        prof = catalog.firmware_profile(proto, "de")
        assert prof and prof["note"] and all(f["text"].strip() for f in prof["files"])
    assert [f["name"] for f in catalog.firmware_profile("macs")["files"]] == ["macs-analysis.example.yaml", "macs_recorder.h"]


def test_firmware_files_are_shipped_with_the_package():
    import tomllib
    from pathlib import Path
    pkg = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]
    assert "firmware/*" in pkg["device_bus_analyzer"] and "catalog.yaml" in pkg["device_bus_analyzer"]
    assert catalog.firmware_file("../catalog.yaml") is None and catalog.firmware_file("secrets.yaml") is None


# --- storage: additive, secrets, no deletion ---------------------------------------------------
def test_existing_database_is_not_changed_by_the_new_schema(tmp_path):
    p = tmp_path / "old.sqlite"
    s = Store(p)
    fill(s)
    s.db.execute("DROP TABLE devices")                      # an installation from before device management
    s.db.commit()
    s.close()
    before = snapshot(p)
    assert before["bursts"]
    s2 = Store(p)
    s2.seed_devices([Device("dw", "board.lan", 6053, "bshdbus", KEY)])
    s2.close()
    assert snapshot(p) == before                            # byte-for-byte the same data in every old table


def test_seed_imports_env_once_and_never_overwrites(store):
    created = store.seed_devices([Device("dw", "board.lan", 6053, "bshdbus", KEY), Device("dry", "dry.lan", 6053, "macs", None)])
    assert created == ["dw", "dry"]
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "other.lan", 6054, None)       # edited in the UI
    assert store.seed_devices([Device("dw", "board.lan", 6053, "bshdbus", "ZZZ")]) == []           # restart with old env
    d = store.device("dw")
    assert (d["host"], d["port"], d["type"], d["manufacturer"]) == ("other.lan", 6054, "dishwasher", "Neff")
    assert {c.name: c.key for c in store.connections()}["dw"] == KEY                                  # stored key wins over env
    store.seed_devices([Device("dry", "dry.lan", 6053, "macs", KEY2)])                              # missing key is filled in
    assert {c.name: c.key for c in store.connections()} == {"dw": KEY, "dry": KEY2}


def test_seed_with_protocol_conflict_keeps_data(store):
    fill(store)                                             # source "dw" stored as bshdbus
    assert store.seed_devices([Device("dw", "h", 6053, "macs", None)]) == []
    assert len(store.frames("dw")) == 3 and store.device("dw")["configured"] is False


def test_save_device_keeps_or_clears_key_and_hides_it(store):
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "h", 6053, KEY)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "h2", 6053, None)             # key=None keeps
    assert store.connections()[0].key == KEY and store.connections()[0].host == "h2"
    assert "key" not in store.device("dw") and store.device("dw")["has_key"] is True
    assert not any("key" in r for r in store.sources())
    store.save_device("dw", "bshdbus", None, None, None, "h2", 6053, None, clear_key=True)
    assert store.connections()[0].key is None and store.device("dw")["has_key"] is False


def test_adopting_an_import_only_source_keeps_its_data(store):
    sid = fill(store)
    assert store.device("dw")["configured"] is False
    assert store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "board.lan") == sid
    assert len(store.frames("dw")) == 3 and store.sources()[0]["model"] == "S413"
    with pytest.raises(ValueError):
        store.save_device("dw", "macs", None, None, None, "x")                                     # decoder cannot change under data
    assert len(store.frames("dw")) == 3


def test_connections_only_enabled_with_host(store):
    store.save_device("a", "bshdbus", None, None, None, "h", 6053, None, enabled=False)
    store.save_device("b", "bshdbus", None, None, None, "", 6053, None)
    store.save_device("c", "macs", None, None, None, "h", 6053, None)
    assert [c.name for c in store.connections()] == ["c"]


def test_validation():
    ok = config.validate_device_input("dw-1", "board.lan", "6053", "bshdbus", KEY, ("bshdbus",))
    assert ok == (6053, KEY)
    assert config.validate_device_input("dw", "h", "", "bshdbus", "", ("bshdbus",)) == (6053, None)
    for args, code in [(("bad name", "h", "1", "bshdbus", ""), "bad_name"), (("a", "h", "1", "nope", ""), "bad_protocol"),
                       (("a", "h h", "1", "bshdbus", ""), "bad_host"), (("a", "h", "70000", "bshdbus", ""), "bad_port"),
                       (("a", "h", "x", "bshdbus", ""), "bad_port"), (("a", "h", "1", "bshdbus", "abc="), "bad_key")]:
        with pytest.raises(ValueError, match=code):
            config.validate_device_input(*args, ("bshdbus",))


def test_delete_device_removes_everything_of_that_device_only(store, tmp_path):
    fill(store, "a")
    fill(store, "b")
    store.ingest_line(store.source("a", "bshdbus"), "[00:00:00.000][I][dbus_raw:1]: HB1 seq=3 t_us=5000 epoch=1800000000 bytes=1 bursts=3 ok=1 crc=0 noack=0 rest=0", 1.8e9)
    store.save_device("a", "bshdbus", "dishwasher", "Neff", "S413", "h", 6053, KEY)
    store.db.execute("INSERT INTO gaps(source_id, recv_ts, message) VALUES((SELECT id FROM sources WHERE name='a'), 1, 'x')")
    store.db.commit()
    keep = len(store.frames("b"))
    counts = store.data_counts("a")
    assert counts["bursts"] == 3 and counts["frames"] == 3 and counts["heartbeats"] == 1 and counts["gaps"] == 1
    assert store.delete_device("a") == counts
    assert store.source_by_name("a") is None and store.data_counts("a") is None and store.device("a") is None
    for table, col in (("frames", "source_id"), ("gaps", "source_id"), ("sessions", "source_id"), ("devices", "source_id")):
        assert store.db.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} NOT IN (SELECT id FROM sources)").fetchone()[0] == 0, table
    assert store.db.execute("SELECT COUNT(*) FROM bursts WHERE session_id NOT IN (SELECT id FROM sessions)").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM heartbeats WHERE session_id NOT IN (SELECT id FROM sessions)").fetchone()[0] == 0
    assert len(store.frames("b")) == keep == 3 and store.connections() == []         # the other device is untouched
    assert store.delete_device("a") is None
    store.save_device("a", "bshdbus", None, None, None, "h")                         # same name again starts empty
    assert store.data_counts("a")["frames"] == 0


def test_set_enabled_keeps_data(store):
    fill(store)
    store.save_device("dw", "bshdbus", None, None, None, "h", 6053, KEY)
    assert store.set_enabled("dw", False) and store.connections() == [] and len(store.frames("dw")) == 3
    assert store.set_enabled("dw", True) and len(store.connections()) == 1 and store.set_enabled("nope", True) is False


def test_last_seen_comes_from_heartbeat_or_board_clock(store):
    sid = fill(store)
    assert store.device("dw")["last_seen"] is not None
    store.ingest_line(sid, "[00:00:00.000][I][dbus_raw:1]: HB1 seq=3 t_us=9000000 epoch=1800000500 bytes=1 bursts=3 ok=1 crc=0 noack=0 rest=0", 1_800_000_500.0)
    assert store.device("dw")["last_seen"] >= 1_800_000_500.0


# --- web dialog -------------------------------------------------------------------------------
@pytest.fixture
def client(store):
    fill(store)
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456",
                 devices=[Device("env", "env.lan", 6053, "macs", KEY)])
    return TestClient(create_app(s, store), follow_redirects=False)


def login(c):
    csrf = re.search(r'name="csrf" value="([^"]+)"', c.get("/login").text).group(1)
    assert c.post("/login", data={"email": MAIL, "password": PW, "csrf": csrf}).status_code == 303
    return re.search(r'action="/logout".*?value="([^"]+)"', c.get("/").text, re.S).group(1)


def test_env_devices_appear_in_ui_and_key_is_never_rendered(client):
    token = login(client)
    html = client.get("/devices").text
    assert "env.lan" in html and KEY not in html and "dw" in html
    assert KEY not in client.get("/").text and KEY not in client.get("/api/sources", headers={"Authorization": "Bearer tok-123456"}).text
    assert token  # csrf token present in the dialog form
    assert 'name="csrf"' in html and "device-dialog" in html and "/static/devices.js" in html


def test_create_edit_flow_and_collectors_data_untouched(client, store):
    token = login(client)
    frames_before = len(store.frames("dw"))
    r = client.post("/devices", data={"csrf": token, "name": "dry2", "type": "dryer", "manufacturer": "Electrolux / AEG",
                                      "model": "Z9", "protocol": "macs", "host": "dry2.lan", "port": "6053", "key": KEY2, "enabled": "1"})
    assert r.status_code == 303
    d = store.device("dry2")
    assert (d["type"], d["manufacturer"], d["model"], d["protocol"], d["host"], d["has_key"]) == ("dryer", "Electrolux / AEG", "Z9", "macs", "dry2.lan", True)
    # edit: protocol in the form is ignored, empty key keeps the stored one, disabled box pauses
    r = client.post("/devices/dry2", data={"csrf": token, "type": "dryer", "manufacturer": "Electrolux / AEG", "model": "Z10", "host": "new.lan", "port": "6053"})
    assert r.status_code == 303
    d = store.device("dry2")
    assert (d["model"], d["host"], d["enabled"], d["protocol"]) == ("Z10", "new.lan", False, "macs")
    assert store.db.execute("SELECT key FROM devices WHERE source_id=(SELECT id FROM sources WHERE name='dry2')").fetchone()[0] == KEY2
    # a model typed once is offered again
    assert "Z10" in client.get("/devices").text
    assert len(store.frames("dw")) == frames_before


def test_adopt_import_only_source_via_dialog(client, store):
    token = login(client)
    assert client.post("/devices", data={"csrf": token, "name": "dw", "type": "dishwasher", "manufacturer": "Bosch / Siemens / Neff",
                                         "model": "Neff S413K60S0E", "protocol": "bshdbus", "host": "b.lan", "enabled": "1"}).status_code == 303
    assert len(store.frames("dw")) == 3 and store.device("dw")["model"] == "Neff S413K60S0E"


def test_dialog_errors_keep_entered_values_and_change_nothing(client, store):
    token = login(client)
    n = len(store.devices())
    r = client.post("/devices", data={"csrf": token, "name": "x y", "protocol": "macs", "host": "h", "model": "KeepMe"})
    assert r.status_code == 422 and "KeepMe" in r.text and "data-form=" in r.text
    r = client.post("/devices", data={"csrf": token, "name": "env", "protocol": "macs", "host": "h"})
    assert r.status_code == 422 and len(store.devices()) == n                   # name already configured
    r = client.post("/devices", data={"csrf": token, "name": "ok", "protocol": "macs", "host": "h", "key": "notbase64"})
    assert r.status_code == 422 and store.device("ok") is None
    assert client.post("/devices/nobody", data={"csrf": token, "host": "h"}).status_code == 404


def test_changes_need_session_and_csrf_not_the_api_token(client, store):
    login(client)
    r = client.post("/devices", data={"csrf": "forged", "name": "z", "protocol": "macs", "host": "h"})
    assert r.status_code == 403 and store.device("z") is None
    anon = TestClient(client.app, follow_redirects=False)
    r = anon.post("/devices", data={"csrf": "x", "name": "z", "protocol": "macs", "host": "h"}, headers={"Authorization": "Bearer tok-123456"})
    assert r.status_code == 303 and r.headers["location"] == "/login" and store.device("z") is None
    assert anon.get("/devices").status_code == 303


def test_pages_render_in_both_languages(client):
    login(client)
    assert "Neues Gerät" in client.get("/devices", params={"lang": "de"}).text
    assert "New device" in client.get("/devices", params={"lang": "en"}).text
    home = client.get("/").text
    assert 'id="new-device"' in home and "Sources" not in home and 'class="main"' not in home      # the start page is the device list, no second tab
    anon = TestClient(client.app, follow_redirects=False)
    ro = anon.get("/", headers={"Authorization": "Bearer tok-123456"}).text                         # API token: read-only list, no management
    assert 'href="/s/dw/frames"' in ro and 'id="new-device"' not in ro


# --- collector manager ------------------------------------------------------------------------
class FakeClient:
    _connection = True

    async def connect(self, login=False):
        pass

    def subscribe_logs(self, cb, log_level=None):
        return lambda: None

    async def disconnect(self):
        pass


def test_manager_follows_device_changes(store):
    async def go():
        m = CollectorManager(store, lambda d: FakeClient())
        store.save_device("a", "bshdbus", None, None, None, "h1", 6053, KEY)
        m.sync()
        first = m.tasks["a"][1]
        m.sync()
        assert m.tasks["a"][1] is first                                     # unchanged device keeps its collector
        store.save_device("a", "bshdbus", None, None, None, "h2", 6053, None)
        m.sync()
        await asyncio.sleep(0)
        assert m.tasks["a"][1] is not first and first.cancelled() or first.done()
        assert m.tasks["a"][0].host == "h2"
        store.save_device("a", "bshdbus", None, None, None, "h2", 6053, None, enabled=False)
        m.sync()
        assert m.tasks == {}
        m.stop()
    asyncio.run(go())


# --- web: firmware, delete, pause, UI structure ----------------------------------------------------------
def test_firmware_page_shows_and_serves_only_catalogue_files(client):
    login(client)
    html = client.get("/firmware/macs", params={"lang": "de"}).text
    assert "macs-analysis.example.yaml" in html and "macs_recorder.h" in html and "substitutions:" in html
    assert "Electrolux-Modelle können abweichen" in html and "/static/firmware.js" in html
    r = client.get("/firmware/macs/macs_recorder.h")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.text == catalog.firmware_file("macs_recorder.h")
    assert client.get("/firmware/macs/bshdbus-analysis.example.yaml").status_code == 404          # not part of this protocol's profile
    assert client.get("/firmware/macs/..%2Fcatalog.yaml").status_code == 404
    assert client.get("/firmware/nope").status_code == 404
    assert "bshdbus-analysis.example.yaml" in client.get("/firmware/bshdbus", params={"device": "dw", "new": "1"}).text


def test_firmware_needs_login(client):
    assert client.get("/firmware/macs").status_code == 303 and client.get("/firmware/macs/macs_recorder.h").status_code == 303


def test_creating_a_device_leads_to_its_firmware(client, store):
    token = login(client)
    r = client.post("/devices", data={"csrf": token, "name": "dry3", "type": "dryer", "manufacturer": "AEG", "model": "Z", "protocol": "macs", "host": "h.lan", "enabled": "1"})
    assert r.status_code == 303 and r.headers["location"] == "/firmware/macs?device=dry3&new=1"
    assert "dry3" in client.get(r.headers["location"]).text


def test_delete_needs_confirmation_by_typing_the_name_and_removes_everything(client, store):
    token = login(client)
    html = client.get("/devices/dw/delete").text
    assert "<b>3</b>" in html and 'name="confirm"' in html and "dw" in html
    n = len(store.frames("dw"))
    assert client.post("/devices/dw/delete", data={"csrf": token, "confirm": "wrong"}).status_code == 422
    assert client.post("/devices/dw/delete", data={"csrf": token}).status_code == 422                # field missing
    assert client.post("/devices/dw/delete", data={"csrf": "forged", "confirm": "dw"}).status_code == 403
    assert len(store.frames("dw")) == n and store.source_by_name("dw")
    r = client.post("/devices/dw/delete", data={"csrf": token, "confirm": "dw"})
    assert r.status_code == 303 and r.headers["location"] == "/devices"
    assert store.source_by_name("dw") is None and store.frames("dw") == []
    assert client.get("/devices/dw/delete").status_code == 404 and client.post("/devices/dw/delete", data={"csrf": token, "confirm": "dw"}).status_code == 404


def test_delete_and_toggle_are_not_possible_with_the_api_token_or_anonymously(client, store):
    anon = TestClient(client.app, follow_redirects=False)
    h = {"Authorization": "Bearer tok-123456"}
    assert anon.post("/devices/dw/delete", data={"csrf": "x", "confirm": "dw"}, headers=h).status_code == 303
    assert anon.post("/devices/dw/enabled", data={"csrf": "x"}, headers=h).status_code == 303
    assert anon.get("/devices/dw/delete", headers=h).status_code == 303 and anon.get("/devices", headers=h).status_code == 303   # hosts: login only
    assert store.source_by_name("dw") and len(store.frames("dw")) == 3


def test_pause_and_resume_via_button_keeps_data(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", None, None, None, "h", 6053, KEY)
    assert client.post("/devices/dw/enabled", data={"csrf": token, "enabled": ""}).status_code == 303
    assert store.device("dw")["enabled"] is False and len(store.frames("dw")) == 3
    assert client.post("/devices/dw/enabled", data={"csrf": token, "enabled": "1"}).status_code == 303 and store.device("dw")["enabled"] is True
    assert client.post("/devices/dw/enabled", data={"csrf": "bad"}).status_code == 403
    assert client.post("/devices/nobody/enabled", data={"csrf": token}).status_code == 404


def test_collector_manager_stop_device_drops_late_lines(store):
    async def go():
        m = CollectorManager(store, lambda d: FakeClient())
        store.save_device("a", "bshdbus", None, None, None, "h", 6053, KEY)
        m.sync()
        c = m.tasks["a"][2]
        f = build_frame(0x17, 0x1010, b"\x1c")
        c.on_log(types.SimpleNamespace(message=raw1(1, 10, f).encode()))
        assert c.lines == 1
        m.stop_device("a")
        c.on_log(types.SimpleNamespace(message=raw1(2, 20, f).encode()))              # in flight while the device is deleted
        assert c.lines == 1 and "a" not in m.tasks
    asyncio.run(go())


def test_ui_has_no_misleading_read_only_claims_and_is_responsive(client):
    login(client)
    for path in ("/", "/devices", "/s/dw/frames", "/findings/bshdbus"):
        html = client.get(path, params={"lang": "de"}).text
        assert "nur lesend" not in html and "read-only" not in html.lower() and 'name="viewport"' in html, path
    css = (client.get("/static/app.css")).text
    assert "@media (max-width:700px)" in css and "table.stack" in css and "dialog.sheet" in css
    devices = client.get("/devices", params={"lang": "de"}).text
    for needle in ("Neues Gerät", 'data-step="1"', 'data-step="4"', "Bosch", "Siemens", "Neff", "Electrolux", "AEG", "Firmware", "Löschen"):
        assert needle in devices, needle
    assert 'class="bottom"' in client.get("/s/dw/frames").text and 'data-label=' in client.get("/s/dw/frames").text


def test_washer_is_a_fixed_type_and_every_brand_and_bus_is_offered_for_every_type(client):
    login(client)
    c = catalog.build([])
    assert c["types"]["washer"]["de"] == "Waschmaschine" and c["types"]["washer"]["en"] == "Washing machine"
    html = client.get("/devices?lang=de").text
    dialog = html[html.index('id="device-dialog"'):]
    assert 'value="washer"' in dialog and "Waschmaschine" in dialog
    assert "data-types=" not in dialog                                             # no type filter on the manufacturers
    for brand in ("Bosch", "Siemens", "Neff", "Electrolux", "AEG"):
        assert f'value="{brand}"' in dialog
    sel = dialog[dialog.index('id="proto-wrap"'):dialog.index("</select>")]
    assert 'id="proto-wrap" hidden' not in dialog and "Bussystem" in sel
    assert 'value="bshdbus"' in sel and 'value="macs"' in sel and "Electrolux, AEG" in sel and "Bosch" in sel


def test_any_bus_can_be_chosen_for_a_known_brand(client, store):
    token = login(client)
    r = client.post("/devices", data={"csrf": token, "name": "wm", "type": "washer", "manufacturer": "AEG", "model": "L8FE",
                                      "protocol": "bshdbus", "host": "wm.lan", "port": "6053", "enabled": "1"})
    assert r.status_code == 303 and r.headers["location"].startswith("/firmware/bshdbus")
    assert (store.device("wm")["protocol"], store.device("wm")["type"]) == ("bshdbus", "washer")


def test_own_models_stay_suggested_after_the_device_is_deleted(client, store):
    token = login(client)
    data = {"csrf": token, "name": "wm2", "type": "washer", "manufacturer": "Miele", "model": "WWD 120", "protocol": "macs",
            "host": "wm2.lan", "port": "6053", "enabled": "1"}
    assert client.post("/devices", data=data).status_code == 303
    assert client.post("/devices", data={**data, "name": "wm3"}).status_code == 303
    assert store.own_classifications().count({"type": "washer", "manufacturer": "Miele", "model": "WWD 120", "protocol": "macs"}) == 1
    store.delete_device("wm2"); store.delete_device("wm3")
    mans = {m["name"]: m for m in catalog.build(store.used_classifications())["manufacturers"]}
    assert mans["Miele"]["models"] == ["WWD 120"] and mans["Miele"]["model_types"]["WWD 120"] == ["washer"]
    assert "WWD 120" in client.get("/devices").text


def test_model_suggestions_know_their_type():
    c = catalog.build([{"type": "dryer", "manufacturer": "Neff", "model": "D1", "protocol": "bshdbus"},
                       {"type": None, "manufacturer": "Neff", "model": "Any 1", "protocol": "bshdbus"}])
    neff = {m["name"]: m for m in c["manufacturers"]}["Neff"]
    assert neff["model_types"]["S413K60S0E"] == ["dishwasher"]          # shipped: the brand makes only dishwashers in the catalogue
    assert neff["model_types"]["D1"] == ["dryer"] and neff["model_types"]["Any 1"] == []
