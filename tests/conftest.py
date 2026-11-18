import pytest

from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.store import Store


def raw1(seq, t_us, data: bytes, dt_us=1000):
    return f"[12:00:00.000][I][dbus_raw:077]: RAW1 seq={seq} t_us={t_us} dt_us={dt_us} n={len(data)} hex={data.hex()}"


def hb1(seq, t_us, epoch=0, **k):
    v = dict(bytes=0, bursts=seq, ok=0, crc=0, noack=0, rest=0) | k
    return (f"[12:00:00.000][I][dbus_raw:166]: HB1 seq={seq} t_us={t_us} epoch={epoch} bytes={v['bytes']} "
            f"bursts={v['bursts']} ok={v['ok']} crc={v['crc']} noack={v['noack']} rest={v['rest']}")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


@pytest.fixture
def frame():
    return build_frame
