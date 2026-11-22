from device_bus_analyzer.protocols import bshdbus as b


def test_crc_known_vector():
    assert b.crc16_xmodem(b"123456789") == 0x31C3       # CRC-16/XMODEM check value


def test_build_and_parse_roundtrip():
    f = b.build_frame(0x25, 0x2008, bytes.fromhex("a050580228000228"))
    assert f[0] == 10 and len(f) == 14                  # LL = 2 command bytes + 8 data, total LL + 4
    frames, st = b.parse_burst(f)
    assert len(frames) == 1 and frames[0].crc_ok and frames[0].data.hex() == "a050580228000228"
    assert (frames[0].ds, frames[0].cmd, frames[0].ack) == (0x25, 0x2008, None)
    assert (st.ok, st.crc, st.noack, st.rest) == (1, 0, 1, 0)


def test_ack_byte_is_attached():
    frames, st = b.parse_burst(b.build_frame(0x17, 0x1010, b"\x1c") + b"\x2a")
    assert frames[0].ack == 0x2A and st.noack == 0


def test_non_ack_byte_after_frame_is_rest():
    frames, st = b.parse_burst(b.build_frame(0x17, 0x1010, b"\x1c") + b"\x2b")
    assert frames[0].ack is None and st.noack == 1 and st.rest == 1


def test_two_frames_in_one_burst():
    data = b.build_frame(0x17, 0x1012, bytes(7)) + b.build_frame(0x17, 0x1013, b"\x01") + b"\x1a"
    frames, st = b.parse_burst(data)
    assert [f.key for f in frames] == ["17/1012", "17/1013"]
    assert frames[0].ack is None and frames[1].ack == 0x1A and st.ok == 2


def test_crc_error_resyncs_and_finds_next_frame():
    bad = bytearray(b.build_frame(0x25, 0x2008, bytes(8)))
    bad[-1] ^= 0xFF
    data = bytes(bad) + b.build_frame(0x17, 0x1010, b"\x0d")
    frames, st = b.parse_burst(data)
    # The parser retries from every following byte but reports the damaged spot once.
    assert frames[0].crc_ok is False and frames[-1].crc_ok is True and frames[-1].key == "17/1010"
    assert st.ok == 1 and st.crc == 1 and len([f for f in frames if not f.crc_ok]) == 1


def test_noise_and_truncation_do_not_crash():
    for blob in (b"", b"\x00", b"\xff" * 5, b"\x0a\x25", b.build_frame(0x25, 0x2008, bytes(8))[:-3]):
        frames, st = b.parse_burst(blob)
        assert not any(f.crc_ok for f in frames)


def test_macs_placeholder_keeps_raw():
    from device_bus_analyzer.protocols import macs
    frames, st = macs.parse_burst(b"\x01\x02")
    assert frames == [] and st.rest == 2


def test_one_damaged_spot_is_counted_once_however_many_retries_follow():
    """An aborted transmission followed by the complete repeat: one damaged spot, the repeat is intact."""
    full = b.build_frame(0x25, 0x2008, bytes([210, 0x30, 0x30, 3, 30, 0, 3, 30]))
    data = full[:11] + full + b"\x2a"                 # cut off after 11 bytes, then sent again and acknowledged
    frames, st = b.parse_burst(data)
    assert st.crc == 1 and st.ok == 1
    assert frames[-1].crc_ok and frames[-1].ack == 0x2A and frames[-1].key == "25/2008"


def test_two_separate_damaged_spots_are_counted_twice():
    good = b.build_frame(0x17, 0x1010, b"\x0d")
    bad1 = bytearray(b.build_frame(0x25, 0x2008, bytes(8))); bad1[-1] ^= 0xFF
    bad2 = bytearray(b.build_frame(0x25, 0x2000, b"\x64")); bad2[-2] ^= 0xFF
    frames, st = b.parse_burst(bytes(bad1) + good + bytes(bad2) + good)
    assert st.crc == 2 and st.ok == 2


def test_firmware_example_counts_damaged_spots_once():
    """The ESPHome lambda mirrors parse_burst: one count per damaged spot, reset by the next intact frame (not compiled here)."""
    import pathlib
    y = (pathlib.Path(b.__file__).parents[1] / "firmware" / "bshdbus-analysis.example.yaml").read_text()
    assert "bool beschaedigt = false;" in y and "if (!beschaedigt) {" in y and "beschaedigt = true;" in y
    assert y.index("beschaedigt = false;\n            id(dbus_ok) += 1;") > y.index("beschaedigt = true;")
    assert y.count("id(dbus_crc_err) += 1;") == 1
