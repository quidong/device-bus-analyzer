import asyncio
import types

import pytest
from conftest import hb1, raw1

from device_bus_analyzer import config
from device_bus_analyzer.collector import Collector
from device_bus_analyzer.importer import guess_date, import_file
from device_bus_analyzer.protocols.bshdbus import build_frame


def test_import_file_with_date_from_name(store, tmp_path):
    f = build_frame(0x17, 0x1010, b"\x1c")
    p = tmp_path / "neff_2026-11-18_184038.txt"
    p.write_text("\n".join([raw1(1, 10, f), raw1(2, 20, f), "noise line"]) + "\n")
    assert guess_date(p) == "2026-11-18"
    assert import_file(store, p, "dw", "bshdbus") == {"RAW1": 2}
    assert len(store.frames("dw")) == 2


def test_import_requires_a_date(store, tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("x\n")
    with pytest.raises(ValueError):
        import_file(store, p, "dw", "bshdbus")


def test_import_midnight_rollover(store, tmp_path):
    f = build_frame(0x17, 0x1010, b"\x1c")
    l1 = raw1(1, 10, f).replace("[12:00:00.000]", "[23:59:59.000]")
    l2 = raw1(2, 20, f).replace("[12:00:00.000]", "[00:00:01.000]")
    p = tmp_path / "a.txt"
    p.write_text(l1 + "\n" + l2 + "\n")
    import_file(store, p, "dw", "bshdbus", date="2026-11-18")
    t = [r["ts"] for r in store.frames("dw")]
    assert t[1] - t[0] == pytest.approx(2.0)


def test_parse_devices_and_keys():
    env = {"DBA_KEY_GESCHIRRSPUELER": "abc="}
    d = config.parse_devices("geschirrspueler@board.lan:6053/bshdbus, trockner@10.0.0.9/macs", env)
    assert (d[0].name, d[0].port, d[0].key, d[0].protocol) == ("geschirrspueler", 6053, "abc=", "bshdbus")
    assert (d[1].port, d[1].key) == (6053, None)
    with pytest.raises(ValueError):
        config.parse_devices("broken", env)


def test_load_settings_defaults():
    s = config.load({"ADMIN_EMAIL": " A@B.de "})
    assert s.admin_email == "a@b.de" and s.db_path == "/data/bus.sqlite" and s.devices == []


class FakeClient:
    """Stands in for aioesphomeapi.APIClient; records that only connect/subscribe/disconnect are used."""
    def __init__(self, lines, fail_first=False):
        self.lines, self.calls, self.fail_first = lines, [], fail_first
        self._connection = True

    async def connect(self, login=False):
        self.calls.append("connect")
        if self.fail_first:
            self.fail_first = False
            raise ConnectionError("device off")

    def subscribe_logs(self, cb, log_level=None):
        self.calls.append("subscribe_logs")
        for z in self.lines:
            cb(types.SimpleNamespace(message=z.encode()))
        return lambda: self.calls.append("unsubscribe")

    async def disconnect(self):
        self.calls.append("disconnect")


def test_collector_stores_lines_and_is_read_only(store, monkeypatch):
    f = build_frame(0x17, 0x1010, b"\x1c")
    client = FakeClient([raw1(1, 10, f), hb1(1, 20, epoch=1_800_000_000), "unrelated"])
    dev = config.Device("dw", "h", 6053, "bshdbus")
    c = Collector(store, dev, client_factory=lambda d: client)

    async def go():
        t = asyncio.create_task(c.run_once())
        await asyncio.sleep(0.05)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    asyncio.run(go())
    assert c.lines == 2 and len(store.frames("dw")) == 1
    assert set(client.calls) <= {"connect", "subscribe_logs", "unsubscribe", "disconnect"}


def test_collector_reconnects_after_failure(store):
    dev = config.Device("dw", "h", 6053, "bshdbus")
    clients = [FakeClient([], fail_first=True), FakeClient([raw1(1, 10, build_frame(0x17, 0x1010, b"\x1c"))])]
    c = Collector(store, dev, client_factory=lambda d: clients.pop(0), backoff=(0.01, 0.02))

    async def go():
        stop = asyncio.Event()
        t = asyncio.create_task(c.run_forever(stop))
        for _ in range(100):
            await asyncio.sleep(0.02)
            if c.lines:
                break
        stop.set()
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    asyncio.run(go())
    assert c.lines == 1
