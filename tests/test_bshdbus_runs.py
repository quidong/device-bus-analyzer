"""BSH D-Bus: run end marker (27/2007 = 03), remaining-time bytes and the commands added from the dishwasher recordings.
Synthetic telegrams only; the payloads mirror what was seen on a Neff S413K60S0E, no recording is stored in the repository."""
import pytest
from conftest import raw1

from device_bus_analyzer import spec
from device_bus_analyzer.protocols.bshdbus import build_frame

T0 = 1_000_000.0


def _put(store, sid, n, ts, ds, cmd, data):
    store.ingest_line(sid, raw1(n, n * 1000, build_frame(ds, cmd, data)), ts)


def _run(store, sid, n, t0, *, end_value=3, silent_before_end=0.0, end_cmd=(0x27, 0x2007)):
    """One run: program, start, two remaining-time frames, then the end state frame; returns the next sequence number."""
    _put(store, sid, n, t0, 0x17, 0x1011, b"\x15")
    _put(store, sid, n + 1, t0 + 10, 0x17, 0x1013, b"\x01")
    _put(store, sid, n + 2, t0 + 70, 0x25, 0x2008, bytes([60, 0x44, 0x30, 1, 0, 0, 1, 0]))
    _put(store, sid, n + 3, t0 + 130, 0x25, 0x2008, bytes([59, 0x44, 0x30, 0, 59, 0, 0, 59]))
    _put(store, sid, n + 4, t0 + 190 + silent_before_end, *end_cmd, bytes([end_value]))
    return n + 5


def test_run_ends_at_the_end_marker_frame(store):
    sid = store.source("dw3", "bshdbus")
    n = _run(store, sid, 1, T0)
    _put(store, sid, n, T0 + 190 + 120, 0x25, 0x2012, b"\x00")            # the module's frame two minutes after the end
    _run(store, sid, n + 1, T0 + 5000)
    first, second = store.runs("dw3")
    assert first["end_ts"] == T0 + 190 and first["end_by"] == "marker"
    assert first["end_status"] == "confirmed" and "27/2007" in first["end_evidence"]
    assert first["open"] is False and first["frames"] == 4 and first["program"] == "1 h 65 C"
    assert second["from_ts"] >= first["end_ts"]                           # context never reaches into the previous run


def test_marker_ends_the_newest_run_immediately(store):
    sid = store.source("dw3", "bshdbus")
    _run(store, sid, 1, T0)
    (r,) = store.runs("dw3")
    assert r["open"] is False and r["end_by"] == "marker"                 # no 20 minutes of silence needed


def test_lost_marker_falls_back_to_the_silent_gap(store):
    sid = store.source("dw3", "bshdbus")
    _run(store, sid, 1, T0, end_value=2)                                  # 02 = idle: not the end marker
    _put(store, sid, 6, T0 + 4000, 0x25, 0x2008, bytes(8))               # later frame: the gap has passed
    (r,) = store.runs("dw3")
    assert r["end_by"] == "gap" and r["end_status"] == "assumed" and r["open"] is False
    assert r["end_ts"] == T0 + 190


def test_marker_wins_over_a_collector_outage(store):
    """The collector was offline for half an hour before the end frame: the run still ends at the marker."""
    sid = store.source("dw3", "bshdbus")
    _run(store, sid, 1, T0, silent_before_end=1800)
    (r,) = store.runs("dw3")
    assert r["end_ts"] == T0 + 190 + 1800 and r["end_by"] == "marker"


def test_marker_of_the_next_run_does_not_end_this_one(store):
    sid = store.source("dw3", "bshdbus")
    n = _run(store, sid, 1, T0, end_value=2)                              # first run: marker frame lost
    _run(store, sid, n, T0 + 5000)
    first, second = store.runs("dw3")
    assert first["end_by"] == "gap" and first["end_ts"] == T0 + 190
    assert second["end_by"] == "marker"


def test_marker_frame_with_crc_error_is_ignored(store):
    sid = store.source("dw3", "bshdbus")
    n = _run(store, sid, 1, T0, end_value=2)
    bad = bytearray(build_frame(0x27, 0x2007, b"\x03"))
    bad[-1] ^= 0xFF
    store.ingest_line(sid, raw1(n, n * 1000, bytes(bad)), T0 + 200)
    _put(store, sid, n + 1, T0 + 4000, 0x25, 0x2008, bytes(8))
    (r,) = store.runs("dw3")
    assert r["end_by"] == "gap"


@pytest.mark.parametrize("minutes", [0, 1, 59, 60, 129, 165, 210])
def test_remaining_time_is_hours_and_minutes(minutes):
    data = bytes([minutes, 0x30, 0x30, minutes // 60, minutes % 60, 0, minutes // 60, minutes % 60])
    d = spec.decode("bshdbus", 0x25, 0x2008, data)
    assert d["values"]["remaining_min"] == minutes
    assert d["values"]["remaining_h"] * 60 + d["values"]["remaining_m"] == minutes
    assert {f["name"]: f["status"] for f in d["fields"]} == {
        "remaining_min": "confirmed", "remaining_h": "confirmed", "remaining_m": "confirmed"}


def test_recorded_remaining_time_frame():
    d = spec.decode("bshdbus", 0x25, 0x2008, bytes.fromhex("8150580209000209"))
    assert (d["values"]["remaining_min"], d["values"]["remaining_h"], d["values"]["remaining_m"]) == (129, 2, 9)


def test_spec_names_the_end_marker():
    end = spec.load_spec("bshdbus")["runs"]["end"]
    assert end["marker"] == {**end["marker"], "key": "27/2007", "byte": 0, "value": 3, "status": "confirmed"}
    assert end["status"] == "assumed"                                     # the gap fallback stays a heuristic


@pytest.mark.parametrize("cmd,name,data,status", [
    (0x2009, "heartbeat", b"\x00", "unknown"),
    (0x2015, "start_parameter", bytes.fromhex("0fff"), "unknown"),
    (0x1012, "cmd_1012", bytes.fromhex("00000000031e00"), "confirmed"),
])
def test_new_commands_are_known_with_honest_status(cmd, name, data, status):
    d = spec.decode("bshdbus", 0x25, cmd, data)
    assert d["name"] == name and d["status"] == status


def test_end_marker_command_is_not_called_an_end_marker_alone():
    """25/2013 = ff00 is also sent at power-on, so its spec text must say so."""
    c = spec.load_spec("bshdbus")["_index"]["25/2013"]
    assert "start" in c["title"] and "27/2007 = 03" in c["evidence"]


def test_spec_is_still_consistent():
    assert spec.validate_spec("bshdbus") == []


def test_glued_power_on_burst_is_split_and_door_changes_decode():
    """Several frames glued together with ACK bytes in between (power-on) and a damaged prefix: every intact frame is recovered."""
    from device_bus_analyzer.protocols.bshdbus import parse_burst
    glued = (b"\x00\x00\x54\x54" + build_frame(0x22, 0x7FF1, b"\x10") + build_frame(0x22, 0x7FF1, b"\x10")
             + build_frame(0x17, 0x1007, b"\x01") + b"\x1a" + build_frame(0x24, 0x2006, b"\x02") + b"\x2a"
             + build_frame(0x25, 0x2008, bytes([210, 0x30, 0x30, 3, 30, 0, 3, 30])) + b"\x2a")
    frames, st = parse_burst(glued)
    good = [(f.ds, f.cmd, f.ack) for f in frames if f.crc_ok]
    assert good == [(0x22, 0x7FF1, None), (0x22, 0x7FF1, None), (0x17, 0x1007, 0x1A), (0x24, 0x2006, 0x2A), (0x25, 0x2008, 0x2A)]
    assert st.ok == 5


@pytest.mark.parametrize("byte,closed", [(0x0A, True), (0x02, False)])
def test_door_state_changes_decode_both_ways(byte, closed):
    assert spec.decode("bshdbus", 0x24, 0x2006, bytes([byte]))["values"]["door_closed"] is closed


def test_door_evidence_says_live_while_awake():
    ev = next(c for c in spec.load_spec("bshdbus")["commands"] if c["key"] == "24/2006")["evidence"]
    assert "live" in ev and "switched off" in ev


def test_spec_documents_adaptive_remaining_time_and_phase_pulses():
    cmds = {c["key"]: c["evidence"] for c in spec.load_spec("bshdbus")["commands"]}
    assert "adaptive" in cmds["25/2008"] and "re-estimat" in cmds["25/2005"] and "re-estimated" in cmds["25/2000"]


def test_spec_records_program_echo_and_auto_run_lengths():
    cmds = {c["key"]: c["evidence"] for c in spec.load_spec("bshdbus")["commands"]}
    assert "14 of 15" in cmds["25/2010"] and "110 to 120" in cmds["25/2008"] and "36 min" in cmds["25/2005"]


def test_audit_statuses_after_the_review():
    cmds = {c["key"]: c for c in spec.load_spec("bshdbus")["commands"]}
    assert cmds["25/2010"]["status"] == "assumed"                       # echo is mostly 0e, not reliably 'last used'
    assert cmds["22/7ff1"]["status"] == "assumed" and "ACK" in cmds["22/7ff1"]["evidence"]
    assert cmds["25/2009"]["status"] == "unknown" and "not periodic" in cmds["25/2009"]["evidence"]
    assert [f["name"] for f in cmds["25/1012"]["fields"]] == ["nominal_h", "nominal_m"]
    d = spec.decode("bshdbus", 0x25, 0x1012, bytes([0, 0, 0, 0, 3, 30, 0]))["values"]
    assert d["nominal_h"] == 3 and d["nominal_m"] == 30


def test_previously_missing_commands_are_in_the_spec():
    idx = spec.load_spec("bshdbus")["_index"]
    assert idx["17/1001"]["status"] == "unknown" and idx["25/1013"]["status"] == "unknown"


def test_run_without_program_selection_uses_the_power_on_echo(store):
    """Started without choosing a program: the machine runs the one it announced at power-on (hours earlier)."""
    sid = store.source("dw4", "bshdbus")
    echo = bytes.fromhex("0e0002000500400000a341e1096a20802100e40000")
    _put(store, sid, 1, T0, 0x25, 0x2010, echo)
    _put(store, sid, 2, T0 + 2600, 0x17, 0x1013, b"\x01")
    _put(store, sid, 3, T0 + 2610, 0x25, 0x2008, bytes([210, 0x30, 0x30, 3, 30, 0, 3, 30]))
    (r,) = store.runs("dw4")
    assert r["program"] == "Eco 50 C"
    # an explicit selection before the start still wins
    sid2 = store.source("dw5", "bshdbus")
    _put(store, sid2, 1, T0, 0x25, 0x2010, echo)
    _put(store, sid2, 2, T0 + 2590, 0x17, 0x1011, b"\x15")
    _put(store, sid2, 3, T0 + 2600, 0x17, 0x1013, b"\x01")
    (r2,) = store.runs("dw5")
    assert r2["program"] == "1 h 65 C"


def test_spec_records_the_eco_run_findings():
    idx = spec.load_spec("bshdbus")["_index"]
    assert "Eco 50 C run from the default program" in idx["25/2008"]["evidence"]
    assert "62 min before the announced end" in idx["25/2005"]["evidence"]
    assert idx["25/1012"]["status"] == "confirmed"
    assert "default program" in idx["25/2008"]["evidence"] or "without a selection" in idx["25/2010"]["evidence"]


def test_spec_records_the_eco_run_end():
    idx = spec.load_spec("bshdbus")["_index"]
    assert "207.3 min" in idx["25/2008"]["evidence"]
    assert "119.7 s" in idx["25/2012"]["evidence"]
    assert "seven recorded runs" in spec.load_spec("bshdbus")["runs"]["end"]["marker"]["evidence"]


def test_confirmed_after_the_review_of_the_raw_recordings():
    idx = spec.load_spec("bshdbus")["_index"]
    assert idx["17/1007"]["status"] == "confirmed" and idx["17/1013"]["status"] == "confirmed"
    assert idx["25/2005"]["status"] == "assumed"
    hb = idx["25/2009"]
    assert hb["status"] == "unknown" and "not periodic" in hb["evidence"] and "heartbeat" not in hb["title"].replace("not a fixed-interval heartbeat", "")


def test_progress_is_derived_from_the_remaining_time_in_the_spec():
    idx = spec.load_spec("bshdbus")["_index"]
    assert "100 x (1 - remaining / announced time)" in idx["25/2000"]["evidence"]
    assert "1 h 65 C run (selected after power-on)" in idx["25/2008"]["evidence"]
    assert "fixed per program" in idx["25/2005"]["evidence"]
    assert "5 s later the chosen one" in idx["17/1011"]["evidence"]
    # the formula itself, as used to check the recording
    for rem, total, pct in [(118, 165, 28), (88, 165, 47), (20, 210, 90), (30, 60, 50), (0, 60, 100)]:
        assert round(100 * (1 - rem / total)) == pct


def test_delayed_start_findings_are_recorded_honestly():
    import yaml
    from pathlib import Path
    spec = yaml.safe_load((Path(__file__).parents[1] / "src/device_bus_analyzer/spec/bshdbus.yaml").read_text())
    cmds = {c["key"]: c for c in spec["commands"]}
    assert spec["enums"]["operating_state"]["0x04"].endswith("(assumed)")
    d = cmds["17/1012"]
    assert d["status"] == "assumed" and any(f["name"] == "delay_h" for f in d["fields"])
    assert "delayed start" in cmds["27/2007"]["evidence"]
    assert "delayed start" in cmds["25/2008"]["evidence"]
