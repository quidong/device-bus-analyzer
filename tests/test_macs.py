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


def test_empty_payload_is_not_a_message():
    # every message carries a type byte; LL = 0 only came from a disturbance whose XOR happened to fit
    frames, st = m.parse_burst(m.build_frame(0x22, 0x2A, b""))
    assert frames == [] and st.rest == 5


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
    for p, name in ((1, "Mix Dry"), (2, "Eco"), (3, "Cotton"), (4, "Easy care"), (10, "Refresh")):
        d = spec.decode("macs", 0x22, 0x2A50, prog(p)[1:])
        assert d["values"]["program"] == name and d["status"] == "confirmed"
    assert spec.decode("macs", 0x22, 0x2A50, prog(0x33)[1:])["values"]["program"] == "0x33"


@pytest.mark.parametrize("raw,label", [(0x0B, "off"), (0x01, "on / ready"), (0x02, "running"), (0x04, "paused"), (0x03, "idle (after power-on or programme ended)"), (0x09, "cancelled"), (0x77, "0x77")])
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
    assert rows[1]["decoded"]["values"]["program"] == "Delicates" and rows[1]["decoded"]["sender"]["value"].startswith("user panel")
    runs = store.runs("tr")
    assert len(runs) == 2
    r = runs[0]
    assert r["program"] == "Delicates" and r["start_status"] == "assumed" and r["end_status"] == "assumed" and r["open"] is False
    assert r["frames"] == 8 and runs[1]["program"] == "Sportswear"
    assert runs[1]["from_ts"] > r["end_ts"]


def test_programme_chosen_between_two_merged_starts_names_the_run(store):
    # real recording: start, stop 3 s later, programme chosen, start again within 60 s
    sid = store.source("tr", "macs")
    _ingest(store, sid, 100.0, 1, 0x22, 0x2A, START)
    _ingest(store, sid, 103.0, 2, 0x22, 0x2A, STOP)
    _ingest(store, sid, 110.0, 3, 0x22, 0x2A, prog(2))
    _ingest(store, sid, 140.0, 4, 0x22, 0x2A, START)
    runs = store.runs("tr")
    assert len(runs) == 1 and runs[0]["program"] == "Eco"


def test_resume_after_pause_continues_the_same_run(store):
    # real recording: start, pause 4 s later, 3 h of heartbeats only (bus stays on), resume (same message as start), off
    sid = store.source("tr", "macs")
    n = iter(range(1, 1000))
    _ingest(store, sid, 100.0, next(n), 0x22, 0x2A, START)
    _ingest(store, sid, 100.1, next(n), 0x2A, 0x22, state(2))
    _ingest(store, sid, 104.0, next(n), 0x22, 0x2A, STOP)
    _ingest(store, sid, 104.1, next(n), 0x2A, 0x22, state(4))
    for k in range(10):
        _ingest(store, sid, 110.0 + 300 * k, next(n), 0x2A, 0x22, HEARTBEAT)
    _ingest(store, sid, 3200.0, next(n), 0x22, 0x2A, START)          # resume
    _ingest(store, sid, 3200.1, next(n), 0x2A, 0x22, state(2))
    runs = store.runs("tr")
    assert len(runs) == 1 and runs[0]["frames"] == 16


def test_start_after_a_stopped_programme_is_a_new_run(store):
    sid = store.source("tr", "macs")
    n = iter(range(1, 1000))
    _ingest(store, sid, 100.0, next(n), 0x22, 0x2A, START)
    _ingest(store, sid, 100.1, next(n), 0x2A, 0x22, state(2))
    _ingest(store, sid, 400.0, next(n), 0x2A, 0x22, state(1))        # back to ready, not paused
    _ingest(store, sid, 500.0, next(n), 0x22, 0x2A, START)
    assert len(store.runs("tr")) == 2


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


def test_drying_time_and_delayed_start_are_decoded():
    d = spec.decode("macs", 0x22, 0x2A50, bytes.fromhex("0300000000000132cb012c00000300000100"))
    v = d["values"]
    assert v["drying_time"] == 0x32 and v["delayed_start"] == 300 and v["delayed_start_set"] is True and v["program"] == "Cotton"
    v = spec.decode("macs", 0x22, 0x2A50, bytes.fromhex("030000000000011e4b000000000300000100"))["values"]
    assert v["drying_time"] == 30 and v["delayed_start_set"] is False and v["delayed_start"] == 0


# --- complete runs: phases, end, remaining time, drum status (payloads as seen on the dryer) ---

def state_full(s: int, phase: int = 0, b5: int = 0, b6: int = 0x41, end: int = 0) -> bytes:
    return bytes([0x52, 0x03, s, phase, 0, 0, b5, b6, 0, end])


def remaining(vv: int, cs: int) -> bytes:
    return bytes([0x56, 0x03, 0x00, 0x00, vv, 0x00, cs])


DRUM_ON = bytes.fromhex("12 00 0a c8 06 4a 01 00")
DRUM_IDLE = bytes.fromhex("12 00 00 e6 06 4a 80 00")


def test_phase_and_end_type_are_decoded():
    v = spec.decode("macs", 0x2A, 0x2252, state_full(2, 4, 5, end=0x70)[1:])["values"]
    assert v["state"] == "running" and v["phase"] == "anti-crease" and v["end_type"] == "ended normally (after anti-crease)"
    v = spec.decode("macs", 0x2A, 0x2252, state_full(3, end=0x40)[1:])["values"]
    assert v["state"].startswith("idle") and v["end_type"] == "ended early (laundry already dry)"
    assert spec.decode("macs", 0x2A, 0x2252, state_full(2, 2, 5)[1:])["values"]["phase"] == "cooling"


def test_time_layouts_decode_only_their_own_fields():
    d = spec.decode("macs", 0x2A, 0x2256, remaining(0xAD, 0xCB)[1:])
    assert d["values"] == {"layout": "remaining time", "remaining": 173, "counter_b5": 203} and not d["notes"]
    assert [f["status"] for f in d["fields"] if f["name"] == "remaining"] == ["confirmed"]
    d = spec.decode("macs", 0x2A, 0x2256, bytes.fromhex("03051d"))
    assert d["values"] == {"layout": "anti-crease countdown", "anti_crease_remaining": 29} and not d["notes"]
    assert spec.decode("macs", 0x2A, 0x2256, bytes.fromhex("0302122f9f00"))["values"]["idle_counter"] == 0x122F


def test_drum_command_and_status_are_signed_and_masked():
    assert spec.decode("macs", 0x30, 0x2212, bytes.fromhex("00f874064a0100"))["values"]["speed_setpoint"] == -1932
    assert spec.decode("macs", 0x30, 0x2212, DRUM_ON[1:])["values"]["speed_setpoint"] == 2760
    v = spec.decode("macs", 0x22, 0x3012, bytes.fromhex("038ac90ac80000280190007600000079007a"))["values"]
    assert v["speed"] == 2761 and v["at_setpoint"] is True and v["speed_ramp"] == 2760 and v["temperature"] == 40
    assert (v["motor_current"], v["moisture_a"], v["moisture_b"]) == (400, 121, 122)
    v = spec.decode("macs", 0x22, 0x3012, bytes.fromhex("03008c00a30000270 2df000100000000 0000".replace(" ", "")))["values"]
    assert v["speed"] == 140 and v["at_setpoint"] is False


def test_power_arguments():
    for raw, label in ((0x10, "off"), (0x20, "off after cancel"), (0x00, "synchronise (power-on)")):
        assert spec.decode("macs", 0x22, 0x2A53, bytes([0x03, raw, 0x02, 0, 0]))["values"]["power_arg"] == label


def test_complete_run_ends_at_the_idle_state_with_remaining_time(store):
    # wet run: start, drying with remaining time, cooling, anti-crease, end (state 03), self power-off 5 min later
    sid = store.source("tr", "macs")
    n = iter(range(1, 1000))
    _ingest(store, sid, 100.0, next(n), 0x22, 0x2A, prog(2))
    _ingest(store, sid, 101.0, next(n), 0x2A, 0x22, remaining(0xAF, 0xCD))
    _ingest(store, sid, 110.0, next(n), 0x22, 0x2A, START)
    _ingest(store, sid, 110.1, next(n), 0x2A, 0x22, state_full(2, 1))
    _ingest(store, sid, 111.0, next(n), 0x30, 0x22, DRUM_ON)
    for k in range(20):
        _ingest(store, sid, 140.0 + 60 * k, next(n), 0x2A, 0x22, remaining(0xAD - k, 0xCB - k))
    _ingest(store, sid, 1400.0, next(n), 0x2A, 0x22, state_full(2, 4, 5, end=0x70))
    _ingest(store, sid, 1700.0, next(n), 0x30, 0x22, DRUM_IDLE)
    _ingest(store, sid, 1700.1, next(n), 0x2A, 0x22, state_full(3, end=0x70))
    _ingest(store, sid, 1990.0, next(n), 0x22, 0x2A, bytes.fromhex("53 03 10 02 00 00"))
    _ingest(store, sid, 1990.1, next(n), 0x2A, 0x22, state_full(0x0B, b6=0x03, end=0x70))
    runs = store.runs("tr")
    assert len(runs) == 1
    r = runs[0]
    assert r["end_by"] == "marker" and r["end_ts"] == pytest.approx(1700.1) and r["start_by"] == "command"
    assert r["program"] == "Eco" and (r["remaining_start_min"], r["remaining_end_min"]) == (0xAD, 0xAD - 19)


def test_missed_start_command_falls_back_to_the_drum(store):
    # the board booted too late: no start command, the first telegram is the drum turning
    sid = store.source("tr", "macs")
    n = iter(range(1, 1000))
    _ingest(store, sid, 100.0, next(n), 0x30, 0x22, DRUM_ON)
    for k in range(5):
        _ingest(store, sid, 130.0 + 60 * k, next(n), 0x2A, 0x22, remaining(0x54 - k, 0xCA - k))
        _ingest(store, sid, 131.0 + 60 * k, next(n), 0x30, 0x22, DRUM_ON)
    _ingest(store, sid, 500.0, next(n), 0x2A, 0x22, state_full(3, end=0x70))
    # a later, normally recorded run must not be swallowed or duplicated by the fallback
    _ingest(store, sid, 3000.0, next(n), 0x22, 0x2A, START)
    _ingest(store, sid, 3001.0, next(n), 0x30, 0x22, DRUM_ON)
    _ingest(store, sid, 3300.0, next(n), 0x2A, 0x22, state_full(3, end=0x40))
    runs = store.runs("tr")
    assert [r["start_by"] for r in runs] == ["fallback", "command"]
    a, b = runs
    assert a["start_ts"] == 100.0 and a["end_by"] == "marker" and a["end_ts"] == 500.0 and a["start_status"] == "assumed"
    assert "not recorded" in a["start_evidence"] and a["remaining_start_min"] == 0x54
    assert b["start_ts"] == 3000.0 and b["end_ts"] == 3300.0


def test_drum_shortly_before_a_recorded_start_is_not_a_separate_run(store):
    sid = store.source("tr", "macs")
    _ingest(store, sid, 100.0, 1, 0x30, 0x22, DRUM_ON)
    _ingest(store, sid, 160.0, 2, 0x22, 0x2A, START)
    _ingest(store, sid, 161.0, 3, 0x30, 0x22, DRUM_ON)
    assert [r["start_by"] for r in store.runs("tr")] == ["command"]


def test_silent_gap_ends_a_run_even_if_an_end_state_comes_much_later(store):
    sid = store.source("tr", "macs")
    _ingest(store, sid, 100.0, 1, 0x22, 0x2A, START)
    _ingest(store, sid, 160.0, 2, 0x2A, 0x22, HEARTBEAT)
    _ingest(store, sid, 90000.0, 3, 0x2A, 0x22, state_full(0x0B, b6=0x03))
    runs = store.runs("tr")
    assert len(runs) == 1 and runs[0]["end_by"] == "gap" and runs[0]["end_ts"] == 160.0


def test_idle_drum_command_after_the_end_is_no_run(store):
    # regression: the idle command 00 00 e6 06 4a 80 00 (and 00 ff 1a ...) has a non-zero set point but byte 5 = 80
    sid = store.source("tr", "macs")
    n = iter(range(1, 1000))
    _ingest(store, sid, 100.0, next(n), 0x22, 0x2A, START)
    _ingest(store, sid, 101.0, next(n), 0x30, 0x22, DRUM_ON)
    _ingest(store, sid, 500.0, next(n), 0x2A, 0x22, state_full(3, end=0x50))
    for k, raw in enumerate(("12 00 ff 1a 06 4a 80 00", "12 00 00 00 09 e2 80 00", "12 00 00 e6 06 4a 80 00")):
        _ingest(store, sid, 501.0 + 2 * k, next(n), 0x30, 0x22, bytes.fromhex(raw))
    _ingest(store, sid, 530.0, next(n), 0x2A, 0x22, state_full(0x0B, b6=0x03))
    runs = store.runs("tr")
    assert len(runs) == 1 and runs[0]["end_ts"] == 500.0


def test_frame_with_zero_length_is_a_disturbance_not_a_message():
    real = m.build_frame(0x22, 0x30, bytes.fromhex("12038aab0ac800002e01"))
    frames, st = m.parse_burst(bytes.fromhex("c9202000") + real)       # C9 20 20 00 C9: XOR fits by chance
    assert [(f.ds, f.cmd, f.crc_ok) for f in frames] == [(0x22, 0x3012, True)]
    assert st.rest == 4


def test_operating_hours_and_programme_counter():
    v = spec.decode("macs", 0x2A, 0x2256, bytes.fromhex("03031e2500f9"))["values"]
    assert v == {"layout": "end summary", "operating_hours": 771.7, "programme_count": 249}
    assert spec.decode("macs", 0x2A, 0x2252, state_full(3, end=0x50)[1:])["values"]["end_type"] == "anti-crease ended early"
