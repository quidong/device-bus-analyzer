import pytest

from device_bus_analyzer import spec


@pytest.mark.parametrize("proto", ["bshdbus", "macs"])
def test_specs_are_consistent(proto):
    assert spec.validate_spec(proto) == []


def test_decode_remaining_time():
    d = spec.decode("bshdbus", 0x25, 0x2008, bytes.fromhex("a050580228000228"))
    assert d["name"] == "remaining_time" and d["values"]["remaining_min"] == 0xA0 and d["status"] == "confirmed"


def test_decode_program_enum_and_unknown_value():
    assert spec.decode("bshdbus", 0x17, 0x1010, b"\x1c")["values"]["program"] == "Chef 70 C"
    assert spec.decode("bshdbus", 0x17, 0x1010, b"\x99")["values"]["program"] == "0x99"


def test_decode_door_bit_and_options():
    assert spec.decode("bshdbus", 0x24, 0x2006, b"\x08")["values"]["door_closed"] is True
    assert spec.decode("bshdbus", 0x24, 0x2006, b"\x00")["values"]["door_closed"] is False
    o = spec.decode("bshdbus", 0x17, 0x1000, b"\x00\xc2")["values"]
    assert o == {"vario_speed_plus": True, "intensive_zone": True, "extra_drying": True}


def test_unknown_command_is_marked_unknown():
    d = spec.decode("bshdbus", 0x99, 0x9999, b"\x01")
    assert d["status"] == "unknown" and d["name"] is None


def test_short_data_is_reported_not_raised():
    d = spec.decode("bshdbus", 0x17, 0x1000, b"\x00")
    assert d["values"] == {} and d["notes"]


def test_spec_contains_no_private_data():
    import re
    from importlib import resources
    text = resources.files("device_bus_analyzer").joinpath("spec", "bshdbus.yaml").read_text()
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|([0-9a-f]{2}:){5}[0-9a-f]{2}", text, re.I)
