"""The frame-aligned recorder of the dryer firmware is plain C++; compile it on the host and feed it the same synthetic
telegrams the Python decoder is tested with. Skipped when no C++ compiler is installed."""
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from device_bus_analyzer.logformat import parse_line
from device_bus_analyzer.protocols import macs as m

ROOT = Path(__file__).parent
CXX = shutil.which("g++") or shutil.which("c++") or shutil.which("clang++")
pytestmark = pytest.mark.skipif(CXX is None, reason="no C++ compiler")


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    exe = tmp_path_factory.mktemp("fw") / "macs_recorder_host"
    subprocess.run([CXX, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-o", str(exe), str(ROOT / "firmware" / "macs_recorder_host.cpp")],
                   check=True)
    return exe


def run(harness, lines):
    out = subprocess.run([str(harness)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True).stdout.splitlines()
    bursts = []
    for line in out:
        e = parse_line(line)
        if e and e.get("typ") == "RAW1":
            bursts.append(e["data"])
    state = [x for x in out if x.startswith("STATE")][0].split()
    return bursts, out, state


def msg(dest, src, payload_hex):
    return m.build_frame(dest, src, bytes.fromhex(payload_hex))


def with_ack(f):
    return f + m.build_ack(f)


def test_frame_split_across_uart_callbacks_stays_one_burst(harness):
    f = with_ack(msg(0x22, 0x2A, "50 03 02 00 00 00 02 01 00 4b 00 00 00 00 05 00 00 01 00"))
    bursts, _, _ = run(harness, [f[:7].hex(), f[7:15].hex(), f[15:].hex(), "IDLE"])
    assert bursts == [f]


def test_message_waits_for_its_ack_and_ack_in_next_callback_is_attached(harness):
    f = msg(0x2A, 0x22, "5f 03")
    bursts, _, _ = run(harness, [f.hex(), m.build_ack(f).hex(), "IDLE"])
    assert bursts == [f + m.build_ack(f)]


def test_message_without_ack_is_released_after_idle(harness):
    f = msg(0x2A, 0x22, "5f 03")
    bursts, _, st = run(harness, [f.hex(), "IDLE"])
    assert bursts == [f] and st[-1] == "pending=0"


def test_two_frames_in_one_callback_become_two_bursts(harness):
    a, b = with_ack(msg(0x2A, 0x22, "5f 03")), with_ack(msg(0x22, 0x2A, "51 00 60 00 00 1b 03"))
    bursts, _, _ = run(harness, [(a + b).hex(), "IDLE"])
    assert bursts == [a, b]


def test_garbage_checksum_errors_and_truncation_are_kept_raw(harness):
    good = with_ack(msg(0x2A, 0x22, "5f 03"))
    bad = bytearray(msg(0x22, 0x2A, "51 00 62"))
    bad[-1] ^= 0x55
    stream = b"\x00\x01" + bytes(bad) + good + msg(0x22, 0x2A, "51 00 60 00 00 1b 03")[:-3]
    bursts, out, _ = run(harness, [stream.hex(), "IDLE"])
    assert b"".join(bursts) == stream                           # nothing lost, nothing invented
    assert good in bursts
    frames = [f for b in bursts for f in m.parse_burst(b)[0] if f.crc_ok]
    assert [f.key for f in frames] == ["2a/225f"]


def test_decoded_state_for_home_assistant_and_heartbeat_line(harness):
    lines = [with_ack(msg(0x22, 0x2A, "50 03 02 00 00 00 02 01 00 4b 00 00 00 00 07 00 00 01 00")).hex(),
             with_ack(msg(0x22, 0x2A, "51 00 60 00 00 1b 03")).hex(),
             with_ack(msg(0x2A, 0x22, "52 03 02 01 00 00 00 41 00 00")).hex(),
             msg(0x30, 0x22, "10 00 24").hex(), "IDLE", "HB"]
    bursts, out, st = run(harness, lines)
    assert st[1:5] == ["2", "7", "96", "1"]                       # state running, programme 7, command start, compressor board seen
    hb = [parse_line(x) for x in out if " HB1 " in f" {x} "][0]
    assert hb["typ"] == "HB1" and hb["ok"] == 4 and hb["crc"] == 0 and hb["rest"] == 0 and hb["bursts"] == len(bursts) == hb["seq"]


@pytest.mark.parametrize("seed", range(8))
def test_random_stream_random_chunking_loses_nothing(harness, seed):
    rnd = random.Random(seed)
    parts, expected = [], []
    for _ in range(60):
        kind = rnd.random()
        if kind < 0.7:
            f = msg(rnd.choice([0x22, 0x2A, 0x30]), rnd.choice([0x22, 0x2A, 0x30]), bytes([rnd.randrange(0x10, 0x60)] + [rnd.randrange(256) for _ in range(rnd.randrange(0, 30))]).hex())
            unit = with_ack(f) if rnd.random() < 0.8 else f
            expected.append(f)
        else:
            unit = bytes(rnd.choice([x for x in range(256) if x not in (m.MARKER, m.ACK_MARKER)]) for _ in range(rnd.randrange(1, 6)))   # noise without frame/ACK starts is unambiguous
        parts.append(unit)
    stream = b"".join(parts)
    lines = []
    for unit in parts:                                          # random UART chunking; silence only between units
        i = 0
        while i < len(unit):
            n = rnd.randrange(1, 12)
            lines.append(unit[i:i + n].hex())
            i += n
        if rnd.random() < 0.3:
            lines.append("IDLE")
    lines.append("IDLE")
    bursts, _, st = run(harness, lines)
    assert b"".join(bursts) == stream and st[-1] == "pending=0"
    found = [f.raw for b in bursts for f in m.parse_burst(b)[0] if f.crc_ok]
    assert all(e in found for e in expected)                      # every real frame is recovered by the Python parser
