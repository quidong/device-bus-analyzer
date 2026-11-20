"""An idle appliance sends no telegrams: a live connection must still count as online."""
import asyncio
import time

from test_companion import MAIL, PW, login
from fastapi.testclient import TestClient

from device_bus_analyzer.collector import Collector
from device_bus_analyzer.config import Device, Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


def test_contact_makes_the_device_live_without_any_telegram(tmp_path):
    store = Store(tmp_path / "c.sqlite")
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", None, "h.lan", 6053, None)
    client = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="t" * 8), store), follow_redirects=False)
    login(client)
    assert 'class="st waiting"' in client.get("/devices").text or "waiting" in client.get("/devices?lang=en").text
    sid = store.source_by_name("dw")["id"]
    store.touch_contact(sid)
    d = store.devices()[0]
    assert d["frames"] == 0 and time.time() - d["last_seen"] < 5
    assert "collecting" in client.get("/devices?lang=en").text
    store.touch_contact(sid, time.time() - 1000)                  # connection gone for a long time: waiting again
    assert "waiting for device" in client.get("/devices?lang=en").text
    store.delete_device("dw")
    assert store.db.execute("SELECT COUNT(*) FROM contact").fetchone()[0] == 0


def test_collector_records_contact_while_connected(tmp_path, monkeypatch):
    store = Store(tmp_path / "c.sqlite")
    seen = []

    class Fake:
        _connection = True
        async def connect(self, login=True): pass
        def subscribe_logs(self, cb, log_level=None): return lambda: None
        async def disconnect(self): pass

    c = Collector(store, Device(name="dw", host="h", port=6053, protocol="bshdbus", key=None), lambda d: Fake())
    orig = store.touch_contact
    monkeypatch.setattr(store, "touch_contact", lambda sid, ts=None: (seen.append(sid), orig(sid, ts)))

    async def go():
        real = asyncio.sleep
        async def fast(_s): await real(0)
        monkeypatch.setattr(asyncio, "sleep", fast)
        t = asyncio.create_task(c.run_once())
        await real(0.05)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    asyncio.run(go())
    assert len(seen) >= 2 and store.devices()[0]["last_seen"]
