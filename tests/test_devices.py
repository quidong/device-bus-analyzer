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
def test_catalog_is_consistent_and_merges_used_values():
    assert catalog.validate_catalog() == []
    c = catalog.build([{"type": "washer", "manufacturer": "Acme", "model": "X1", "protocol": "bshdbus"},
                       {"type": "dishwasher", "manufacturer": "Bosch / Siemens / Neff", "model": "Own 1", "protocol": "bshdbus"}])
    assert {"dishwasher", "dryer", "washer"} <= set(c["types"])
    mans = {m["name"]: m for m in c["manufacturers"]}
    assert mans["Acme"]["models"] == ["X1"] and "Own 1" in mans["Bosch / Siemens / Neff"]["models"]
    assert mans["Electrolux / AEG"]["protocol"] == "macs" and sorted(c["protocols"]) == ["bshdbus", "macs"]


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
    assert r.status_code == 422 and "KeepMe" in r.text and 'data-open="1"' in r.text
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
    assert "/devices?new=1" in client.get("/").text


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
