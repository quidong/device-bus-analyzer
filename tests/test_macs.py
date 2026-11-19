"""MACS bus (dryer): framing, ACK handling, spec decoding and run detection. Synthetic telegrams only; the payloads
mirror what was seen on an AEG heat-pump dryer, but no recording is stored in the repository."""
import pytest
from conftest import raw1

from device_bus_analyzer import spec
from device_bus_analyzer.protocols import macs as m

HEARTBEAT = bytes.fromhex("5f03")
PROGRAM = "50 03 02 00 00 00 02 01 00 4b 00 00 00 00 {p:02x} 00 00 01 00"
START = bytes.fromhex("51 00 60 00 00 1b 03")
STOP = bytes.fromhex("51 00 62")


def prog(p: int) -> bytes:
    return bytes.fromhex(PROGRAM.format(p=p))


def state(s: int) -> bytes:
    return bytes.fromhex(f"52 03 {s:02x} 00 00 00 00 41 00 00")


def test_checksum_and_build_roundtrip():
    f = m.build_frame(0x2A, 0x22, HEARTBEAT)
    assert f == bytes.fromhex("c9 2a 22 02 5f 03") + bytes([m.checksum(bytes.fromhex("c9 2a 22 02 5f 03"))])
    frames, st = m.parse_burst(f)
    assert len(frames) == 1 and frames[0].crc_ok and frames[0].raw == f
    assert (frames[0].ds, frames[0].cmd, frames[0].data, frames[0].ack) == (0x2A, 0x225F, b"\x03", None)
    assert frames[0].key == "2a/225f"
    assert (st.ok, st.crc, st.noack, st.rest) == (1, 0, 1, 0)


def test_ack_is_attached_only_with_matching_checksum():
    f = m.build_frame(0x2A, 0x22, HEARTBEAT)
    frames, st = m.parse_burst(f + m.build_ack(f))
    assert frames[0].ack == 0x98 and st.noack == 0 and st.rest == 0
    assert m.build_ack(f) == bytes([0x98, f[-1], 0x98 ^ f[-1]])
    bad = bytes([0x98, f[-1] ^ 1, 0x98 ^ f[-1] ^ 1])            # ACK of some other message
    frames, st = m.parse_burst(f + bad)
    assert frames[0].ack is None and st.noack == 1 and st.rest == 3
    frames, st = m.parse_burst(f + bytes([0x98, f[-1], 0x00]))   # ACK with a wrong own checksum
    assert frames[0].ack is None and st.rest == 3


def test_several_messages_in_one_burst():
    a, b = m.build_frame(0x2A, 0x22, HEARTBEAT), m.build_frame(0x22, 0x2A, START)
    frames, st = m.parse_burst(a + m.build_ack(a) + b + m.build_ack(b))
    assert [f.key for f in frames] == ["2a/225f", "22/2a51"] and all(f.ack == 0x98 for f in frames)
    assert frames[1].data == START[1:] and st.ok == 2 and st.rest == 0


def test_checksum_error_is_reported_and_parser_resyncs():
    bad = bytearray(m.build_frame(0x2A, 0x22, state(2)))
    bad[-1] ^= 0xFF
    good = m.build_frame(0x2A, 0x22, HEARTBEAT)
    frames, st = m.parse_burst(bytes(bad) + good)
    assert frames[0].crc_ok is False and frames[-1].crc_ok is True and frames[-1].key == "2a/225f"
    assert st.crc == 1 and st.ok == 1


def test_frame_cut_at_end_of_burst_is_rest_not_guessed():
    f = m.build_frame(0x22, 0x2A, prog(4))
    frames, st = m.parse_burst(f[:-4])
    assert frames == [] and st.rest == len(f) - 4
    frames, st = m.parse_burst(b"\xc9\x2a")                     # marker too close to the end
    assert frames == [] and st.rest == 2


@pytest.mark.parametrize("blob", [b"", b"\x00", b"\xff" * 7, b"\x98\x00\x98", b"\xc9" * 9])
def test_noise_does_not_crash(blob):
    frames, st = m.parse_burst(blob)
    assert not any(f.crc_ok for f in frames)


def test_empty_payload_gets_type_zero():
    frames, _ = m.parse_burst(m.build_frame(0x22, 0x2A, b""))
    assert frames[0].crc_ok and frames[0].cmd == 0x2A00 and frames[0].data == b""


def test_spec_is_consistent_and_has_no_private_data():
    import re
    from importlib import resources
    assert spec.validate_spec("macs") == []
    text = resources.files("device_bus_analyzer").joinpath("spec", "macs.yaml").read_text()
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|([0-9a-f]{2}:){5}[0-9a-f]{2}", text, re.I)


def test_sender_is_read_from_the_wire_with_device_status():
    d = spec.decode("macs", 0x2A, 0x225F, b"\x03", 0x98)
    assert d["sender"]["value"].startswith("dryer control board") and d["sender"]["status"] == "assumed"
    assert d["receiver"]["value"].startswith("user panel")
    assert d["acked_by"]["status"] == "assumed" and d["name"] == "heartbeat" and d["status"] == "confirmed"
    d = spec.decode("macs", 0x22, 0x2A50, prog(4)[1:])
    assert d["sender"]["value"].startswith("user panel") and d["receiver"]["value"].startswith("dryer control board")


def test_program_number_is_decoded():
    for p in (1, 4, 10):
        d = spec.decode("macs", 0x22, 0x2A50, prog(p)[1:])
        assert d["values"]["program"] == f"Programme {p}" and d["status"] == "confirmed"
    assert spec.decode("macs", 0x22, 0x2A50, prog(0x33)[1:])["values"]["program"] == "0x33"


@pytest.mark.parametrize("raw,label", [(0x0B, "off"), (0x01, "on / ready"), (0x02, "running"), (0x04, "paused"), (0x77, "0x77")])
def test_device_state(raw, label):
    d = spec.decode("macs", 0x2A, 0x2252, state(raw)[1:])
    assert d["values"]["state"] == label and d["status"] == "assumed"


def test_panel_commands():
    assert spec.decode("macs", 0x22, 0x2A51, START[1:])["values"]["action"] == "start"
    assert spec.decode("macs", 0x22, 0x2A51, STOP[1:])["values"]["action"] == "stop / pause"


def test_identification_text():
    d = spec.decode("macs", 0x22, 0x3011, bytes.fromhex("00 4d 31 49 42 31 36 30 36 3d d4"))
    assert d["values"]["ident"] == "M1IB1606" and d["status"] == "confirmed"
    assert spec.decode("macs", 0x22, 0x3011, b"\x00M1I")["notes"]


def test_unknown_and_short_messages_are_reported_not_raised():
    d = spec.decode("macs", 0x22, 0x2A99, b"\x01")
    assert d["status"] == "unknown" and d["name"] is None
    assert spec.decode("macs", 0x22, 0x2A50, b"\x03")["notes"]


def _ingest(store, sid, ts, seq, dest, src, payload, ack=True):
    f = m.build_frame(dest, src, payload)
    store.ingest_line(sid, raw1(seq, seq * 1000, f + (m.build_ack(f) if ack else b"")), ts)


def test_store_decodes_frames_and_detects_a_run(store):
    sid = store.source("tr", "macs")
    seq = iter(range(1, 100))
    _ingest(store, sid, 1000.0, next(seq), 0x2A, 0x22, HEARTBEAT)
    _ingest(store, sid, 1005.0, next(seq), 0x22, 0x2A, prog(5))
    _ingest(store, sid, 1010.0, next(seq), 0x22, 0x2A, START)
    _ingest(store, sid, 1010.1, next(seq), 0x22, 0x2A, START)          # repeated start is merged
    _ingest(store, sid, 1010.2, next(seq), 0x2A, 0x22, state(2))
    for k in range(5):
        _ingest(store, sid, 1013.0 + 3 * k, next(seq), 0x2A, 0x22, HEARTBEAT)
    _ingest(store, sid, 5000.0, next(seq), 0x22, 0x2A, prog(7))
    _ingest(store, sid, 5010.0, next(seq), 0x22, 0x2A, START)
    rows = store.frames("tr", limit=100)
    assert len(rows) == 12 and all(r["crc_ok"] and r["ack"] == 0x98 for r in rows)
    assert rows[1]["decoded"]["values"]["program"] == "Programme 5" and rows[1]["decoded"]["sender"]["value"].startswith("user panel")
    runs = store.runs("tr")
    assert len(runs) == 2
    r = runs[0]
    assert r["program"] == "Programme 5" and r["start_status"] == "assumed" and r["end_status"] == "assumed" and r["open"] is False
    assert r["frames"] == 8 and runs[1]["program"] == "Programme 7"
    assert runs[1]["from_ts"] > r["end_ts"]


def test_programme_chosen_between_two_merged_starts_names_the_run(store):
    # real recording: start, stop 3 s later, programme chosen, start again within 60 s
    sid = store.source("tr", "macs")
    _ingest(store, sid, 100.0, 1, 0x22, 0x2A, START)
    _ingest(store, sid, 103.0, 2, 0x22, 0x2A, STOP)
    _ingest(store, sid, 110.0, 3, 0x22, 0x2A, prog(2))
    _ingest(store, sid, 140.0, 4, 0x22, 0x2A, START)
    runs = store.runs("tr")
    assert len(runs) == 1 and runs[0]["program"] == "Programme 2"


def test_rebuild_frames_reproduces_the_same_result(store):
    sid = store.source("tr", "macs")
    _ingest(store, sid, 10.0, 1, 0x2A, 0x22, HEARTBEAT)
    _ingest(store, sid, 13.0, 2, 0x22, 0x2A, START)
    before = [(r["ds"], r["cmd"], r["data"], r["ack"]) for r in store.frames("tr")]
    store.rebuild_frames()
    assert [(r["ds"], r["cmd"], r["data"], r["ack"]) for r in store.frames("tr")] == before


def test_spec_lists_the_known_devices():
    s = spec.load_spec("macs")
    assert {"22", "2a", "30", "00"} <= set(s["devices"]) and all(v["status"] in spec.STATUS for v in s["devices"].values())
