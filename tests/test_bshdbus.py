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
    # Like the firmware, the parser retries from every following byte, so bogus candidates may add more
    # CRC failures ("CRC!" noise). What matters: the first candidate fails and the real next frame is found.
    assert frames[0].crc_ok is False and frames[-1].crc_ok is True and frames[-1].key == "17/1010"
    assert st.ok == 1 and st.crc == len([f for f in frames if not f.crc_ok]) >= 1


def test_noise_and_truncation_do_not_crash():
    for blob in (b"", b"\x00", b"\xff" * 5, b"\x0a\x25", b.build_frame(0x25, 0x2008, bytes(8))[:-3]):
        frames, st = b.parse_burst(blob)
        assert not any(f.crc_ok for f in frames)


def test_macs_placeholder_keeps_raw():
    from device_bus_analyzer.protocols import macs
    frames, st = macs.parse_burst(b"\x01\x02")
    assert frames == [] and st.rest == 2
