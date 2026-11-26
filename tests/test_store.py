from conftest import hb1, raw1

from device_bus_analyzer.protocols.bshdbus import build_frame


def feed(store, sid, *lines):
    for i, z in enumerate(lines):
        store.ingest_line(sid, z, 1000.0 + i)


def test_ingest_stores_raw_and_frames(store):
    sid = store.source("dw", "bshdbus")
    f = build_frame(0x25, 0x2008, bytes.fromhex("a050580228000228"))
    assert store.ingest_line(sid, raw1(1, 5_000_000, f + b"\x2a"), 1000.0) == "RAW1"
    assert store.ingest_line(sid, "[12:00:00.000][S][sensor]: 'Restzeit' >> 160 min", 1000.0) is None
    fr = store.frames("dw")
    assert len(fr) == 1 and fr[0]["crc_ok"] == 1 and fr[0]["ack"] == 0x2A
    assert fr[0]["decoded"]["values"]["remaining_min"] == 160
    assert store.bursts("dw")[0]["data"] == f + b"\x2a"


def test_heartbeat_epoch_gives_absolute_time(store):
    sid = store.source("dw", "bshdbus")
    feed(store, sid, hb1(0, 1_000_000, epoch=1_800_000_001), raw1(1, 3_000_000, build_frame(0x17, 0x1010, b"\x1c")))
    ts = store.frames("dw")[0]["ts"]
    assert abs(ts - (1_800_000_001 - 1.0 + 3.0)) < 1e-6        # boot_epoch = epoch - t_us/1e6


def test_without_epoch_receive_time_is_used(store):
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 3_000_000, build_frame(0x17, 0x1010, b"\x1c")), 1234.5)
    assert store.frames("dw")[0]["ts"] == 1234.5


def test_gap_in_sequence_is_recorded(store):
    sid = store.source("dw", "bshdbus")
    f = build_frame(0x17, 0x1010, b"\x1c")
    feed(store, sid, raw1(1, 10, f), raw1(2, 20, f), raw1(5, 30, f))
    assert "2 -> 5 (2 bursts missing)" in store.quality("dw")["gaps"][0]["message"]


def test_heartbeat_seq_mismatch_is_a_gap(store):
    sid = store.source("dw", "bshdbus")
    feed(store, sid, raw1(1, 10, build_frame(0x17, 0x1010, b"\x1c")), hb1(4, 60_000_000))
    assert any("bursts lost" in g["message"] for g in store.quality("dw")["gaps"])


def test_board_restart_starts_new_session_without_gap(store):
    sid = store.source("dw", "bshdbus")
    f = build_frame(0x17, 0x1010, b"\x1c")
    feed(store, sid, raw1(7, 9_000_000, f), raw1(1, 1_000_000, f), raw1(2, 2_000_000, f))
    q = store.quality("dw")
    assert q["sessions"] == 2 and q["gaps"] == []


def test_broken_raw_line_is_logged_not_stored(store):
    sid = store.source("dw", "bshdbus")
    assert store.ingest_line(sid, "RAW1 seq=1 t_us=5 dt_us=5 n=3 hex=ff", 1.0) == "BROKEN"
    assert store.bursts("dw") == [] and "broken" in store.quality("dw")["gaps"][0]["message"]


def test_timeline_shows_only_changes_and_skips_crc_errors(store):
    sid = store.source("dw", "bshdbus")
    a, b_ = (build_frame(0x25, 0x2008, bytes([m]) + bytes(7)) for m in (160, 159))
    bad = bytearray(a); bad[-1] ^= 1
    feed(store, sid, raw1(1, 10, a), raw1(2, 20, a), raw1(3, 30, bytes(bad)), raw1(4, 40, b_))
    tl = store.timeline("dw")
    assert [t["decoded"]["values"]["remaining_min"] for t in tl] == [160, 159]


def test_command_stats_and_values(store):
    sid = store.source("dw", "bshdbus")
    f = build_frame(0x17, 0x1010, b"\x1c")
    feed(store, sid, raw1(1, 10, f), raw1(2, 20, f))
    cs = store.command_stats("dw")
    assert cs[0]["n"] == 2 and cs[0]["distinct_values"] == 1 and cs[0]["decoded"]["name"] == "program_select_early"
    assert store.command_values("dw", 0x17, 0x1010)[0]["n"] == 2


def test_rebuild_frames_is_idempotent_and_keeps_raw(store):
    sid = store.source("dw", "bshdbus")
    f = build_frame(0x17, 0x1010, b"\x1c")
    feed(store, sid, raw1(1, 10, f + b"\x1a"), raw1(2, 20, f))
    before = [(r["ds"], r["cmd"], r["data"], r["ack"]) for r in store.frames("dw")]
    assert store.rebuild_frames() == 2 and store.rebuild_frames() == 2
    assert [(r["ds"], r["cmd"], r["data"], r["ack"]) for r in store.frames("dw")] == before
    assert len(store.bursts("dw")) == 2


def test_legacy_frame_lines_are_stored_as_frames_only(store):
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, "[12:00:00.000][I][dbus_raw:99]: FRAME 252008a050580228000228 OK ACK 2A", 50.0)
    store.ingest_line(sid, "[12:00:00.000][D][main:632]: Received frame dest 0x17 cmd 0x1010: 0x1c", 51.0)
    fr = store.frames("dw")
    assert [(f["ds"], f["cmd"]) for f in fr] == [(0x25, 0x2008), (0x17, 0x1010)] and store.bursts("dw") == []


def test_protocol_mismatch_and_unknown_protocol(store):
    import pytest
    store.source("dw", "bshdbus")
    with pytest.raises(ValueError):
        store.source("dw", "macs")
    with pytest.raises(ValueError):
        store.source("x", "nope")


def test_frame_filters_and_limits(store):
    sid = store.source("dw", "bshdbus")
    feed(store, sid, *(raw1(i, i * 10, build_frame(0x17, 0x1010 + i % 2, b"\x1c")) for i in range(1, 7)))
    assert len(store.frames("dw", cmd=0x1011)) == 3
    assert len(store.frames("dw", limit=2)) == 2
    assert store.frames("nobody") == []


def test_legacy_received_and_frame_are_not_double_counted(tmp_path):
    from device_bus_analyzer.store import Store
    st = Store(tmp_path / "d.sqlite")
    sid = st.source("x", "bshdbus")
    st.ingest_line(sid, "[22:29:46.909][D][main:720]: Received frame dest 0x25 cmd 0x2008: 0x8150", 100.0)
    st.ingest_line(sid, "[22:29:46.920][D][main:720]: Received frame dest 0x25 cmd 0x2000: 0x13", 100.01)
    st.ingest_line(sid, "FRAME 252008" "8150 OK ACK 2A", 100.03)
    st.ingest_line(sid, "FRAME 25200013 OK ACK 2A", 100.04)
    rows = st.db.execute("SELECT cmd, ack FROM frames ORDER BY id").fetchall()
    assert [(r["cmd"], r["ack"]) for r in rows] == [(0x2008, 0x2A), (0x2000, 0x2A)]
    # a RECEIVED line without a partner stays; identical repeats later than 2 s are separate frames
    st.ingest_line(sid, "[22:29:50.000][D][main:720]: Received frame dest 0x25 cmd 0x2000: 0x13", 110.0)
    st.ingest_line(sid, "FRAME 25200013 OK ACK 2A", 120.0)
    assert st.db.execute("SELECT count(*) FROM frames").fetchone()[0] == 4


def test_quality_separates_repeated_damaged_spots_from_lost_ones(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    full = build_frame(0x25, 0x2008, bytes(8))
    lost = build_frame(0x25, 0x2000, b"\x64")
    store.ingest_line(sid, raw1(1, 1000, full[:9] + full + b"\x2a"), 1_000_000.0)       # aborted, repeated intact
    store.ingest_line(sid, raw1(2, 2000, lost[:-1] + b"\x00"), 1_000_100.0)             # damaged, never repeated
    q = store.quality("dw")
    assert q["crc_errors"] == 2 and q["not_repeated"] == 1 and q["ok"] == 1


def test_frames_received_before_the_first_clock_time_get_their_board_time(store):
    # a buffered board replays its first bursts late; their receive time is wrong, t_us is right
    from conftest import hb1, raw1
    from device_bus_analyzer.protocols import macs as m
    sid = store.source("tr", "macs")
    f = m.build_frame(0x2A, 0x22, bytes.fromhex("5f03"))
    store.ingest_line(sid, raw1(1, 1_000_000, f), 5000.0)       # sent at boot + 1 s, received 40 s later
    store.ingest_line(sid, raw1(2, 4_000_000, f), 5000.1)
    assert [r["ts"] for r in store.frames("tr")] == [5000.0, 5000.1]
    store.ingest_line(sid, hb1(2, 41_000_000, epoch=1_800_000_041), 5001.0)
    assert [r["ts"] for r in store.frames("tr")] == [1_800_000_001.0, 1_800_000_004.0]


def test_quality_is_split_into_raw_and_legacy_data(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    # legacy firmware: decoded lines only, no burst: one "CRC!" line per resync retry
    for i in range(3):
        store.ingest_line(sid, "[00:00:00.000][I][dbus_raw:1]: FRAME 25200800 CRC! (soll 0001 ist 0002)", 1_000_000.0 + i)
    store.ingest_line(sid, "[00:00:00.000][I][dbus_raw:1]: FRAME 252008d23030 OK ACK 2A", 1_000_010.0)
    # raw bursts: one damaged spot, repeated intact
    full = build_frame(0x25, 0x2008, bytes(8))
    store.ingest_line(sid, raw1(1, 1000, full[:9] + full + b"\x2a"), 1_000_100.0)
    q = store.quality("dw")
    assert q["raw"]["crc_errors"] == 1 and q["raw"]["ok"] == 1 and q["raw"]["not_repeated"] == 0
    assert q["legacy"]["crc_errors"] == 3 and q["legacy"]["ok"] == 1
    assert q["frames"] == q["raw"]["frames"] + q["legacy"]["frames"] and q["crc_errors"] == 4


def test_command_list_hides_entries_seen_only_as_damaged_candidates(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    good = build_frame(0x25, 0x2008, bytes(8))
    bad = bytearray(build_frame(0x17, 0x1010, b"\x0d")); bad[-1] ^= 0xFF
    store.ingest_line(sid, raw1(1, 1000, good + b"\x2a" + bytes(bad)), 1_000_000.0)
    keys = lambda rows: {(r["ds"], r["cmd"]) for r in rows}
    assert keys(store.command_stats("dw")) == {(0x25, 0x2008)}
    assert keys(store.command_stats("dw", include_damaged=True)) == {(0x25, 0x2008), (0x17, 0x1010)}
    assert store.damaged_only_commands("dw") == 1


def test_purge_legacy_removes_only_frames_without_raw_data(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 1000, build_frame(0x25, 0x2008, bytes(8)) + b"\x2a"), 1_000_000.0)
    store.db.execute("INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) VALUES(?,?,?,?,?,?,?,?,?)",
                     (sid, None, None, 1.0, 0x25, 0x2000, b"\x01", 1, None))
    store.db.commit()
    assert store.purge_legacy("dw") == 1
    assert store.purge_legacy("dw") == 0
    assert [(r["ds"], r["cmd"]) for r in store.command_stats("dw", include_damaged=True)] == [(0x25, 0x2008)]
    assert store.purge_legacy("unknown") == 0


def test_damaged_frames_are_not_interpreted(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    bad = bytearray(build_frame(0x25, 0x2008, bytes([0xD2, 0x30, 0x30, 0, 0x1E, 0, 3, 0x1E]))); bad[-1] ^= 0xFF
    store.ingest_line(sid, raw1(1, 1000, bytes(bad)), 1_000_000.0)
    rows = store.frames("dw")
    assert rows and not rows[0]["crc_ok"]
    d = rows[0]["decoded"]
    assert d["name"] is None and d["values"] == {} and d["sender"]["value"] is None and d["status"] == "unknown"


def test_frames_are_rederived_once_when_the_parser_version_changes(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 1000, build_frame(0x25, 0x2008, bytes(8)) + b"\x2a"), 1_000_000.0)
    store.db.execute("INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) "
                     "SELECT source_id, session_id, burst_id, ts, 1, 2, x'00', 0, NULL FROM frames LIMIT 1")   # stale candidate
    store.db.commit()
    assert store.ensure_frames_current() == 1
    assert [(r["ds"], r["crc_ok"]) for r in store.frames("dw")] == [(0x25, 1)]
    assert store.ensure_frames_current() is None


def test_decoded_lines_that_repeat_a_raw_frame_are_not_stored_twice(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    fr = build_frame(0x25, 0x2008, bytes([1, 2, 3, 4, 5, 6, 7, 8]))
    store.ingest_line(sid, raw1(1, 1000, fr + b"\x2a"), 1_000_000.0)
    store.ingest_line(sid, "Received frame dest 0x25 cmd 0x2008: 0x0102030405060708", 1_000_001.0)
    assert len(store.frames("dw")) == 1
    store.ingest_line(sid, "Received frame dest 0x25 cmd 0x2008: 0x0102030405060708", 1_000_900.0)   # much later: a real new frame
    assert len(store.frames("dw")) == 2


def test_rederive_removes_existing_legacy_duplicates(store):
    from conftest import raw1
    from device_bus_analyzer.protocols.bshdbus import build_frame
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 1000, build_frame(0x25, 0x2008, bytes(8)) + b"\x2a"), 1_000_000.0)
    ts = store.frames("dw")[0]["ts"]
    store.db.execute("INSERT INTO frames(source_id, session_id, burst_id, ts, ds, cmd, data, crc_ok, ack) VALUES(?,?,?,?,?,?,?,?,?)",
                     (sid, None, None, ts + 0.5, 0x25, 0x2008, bytes(8), 1, None))
    store.db.commit()
    assert len(store.frames("dw")) == 2
    store.ensure_frames_current()
    assert len(store.frames("dw")) == 1
