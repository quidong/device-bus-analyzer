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


def test_sender_is_derived_with_status():
    d = spec.decode("bshdbus", 0x17, 0x1010, b"\x1c")
    assert d["sender"] == {"value": "control panel", "status": "assumed", "evidence": d["sender"]["evidence"]}
    assert d["receiver"]["value"] == "power module"
    d = spec.decode("bshdbus", 0x25, 0x2008, bytes(8))
    assert d["sender"]["value"] == "power module" and d["sender"]["status"] == "assumed"


def test_unknown_destination_class_gives_unknown_sender():
    d = spec.decode("bshdbus", 0x9F, 0x0001, b"")
    assert d["sender"]["value"] is None and d["sender"]["status"] == "unknown"
    assert spec.decode("macs", 0x01, 0x0001, b"")["sender"]["status"] == "unknown"


def test_exact_node_entry_beats_class_entry(monkeypatch):
    s = spec.load_spec("bshdbus")
    monkeypatch.setitem(s["nodes"], "17", {"sender": "x", "receiver": "y", "status": "confirmed", "evidence": "e"})
    assert spec.decode("bshdbus", 0x17, 0x1010, b"\x1c")["sender"] == {"value": "x", "status": "confirmed", "evidence": "e"}


def test_ack_node_is_derived_and_marked_assumed():
    assert spec.decode("bshdbus", 0x17, 0x1010, b"\x1c", ack=0x1A)["acked_by"]["value"] == "control panel"
    d = spec.decode("bshdbus", 0x25, 0x2008, bytes(8), ack=0x2A)["acked_by"]
    assert d["value"] == "power module" and d["status"] == "assumed"
    assert spec.decode("bshdbus", 0x25, 0x2008, bytes(8), ack=0x7A)["acked_by"]["status"] == "unknown"
    assert spec.decode("bshdbus", 0x25, 0x2008, bytes(8))["acked_by"] is None


def test_every_field_carries_its_own_status():
    d = spec.decode("bshdbus", 0x24, 0x2006, b"\x0a")
    st = {f["name"]: f["status"] for f in d["fields"]}
    assert st == {"door_closed": "confirmed", "rinse_aid_flag": "assumed", "salt_flag": "assumed"}
