"""Export, validation and spec suggestion of accepted findings; every file in contributions/ must pass the check."""
import json
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from test_companion import MAIL, PW, T0, door, door_markers, login, put_frames, series  # noqa: F401

from device_bus_analyzer import cli, contribution, spec
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app

GOOD = {"format": 1, "protocol": "bshdbus", "type": "dishwasher", "manufacturer": "Neff", "model": "S413K60S0E",
        "findings": [{"meaning": "Tür geöffnet", "action": "door_open", "ds": 0x17, "cmd": 0x1010, "byte": 2, "from": 0, "to": 1, "repeats": 3, "of": 3, "status": "confirmed"},
                     {"meaning": "Program 3", "action": "program", "ds": 0x17, "cmd": 0x1011, "byte": 0, "from": 3, "to": 0x1c, "repeats": 4, "of": 4, "status": "assumed"}],
        "values": [{"meaning": "Restzeit", "unit": "min", "ds": 0x25, "cmd": 0x2008, "byte": 0, "encoding": "u8", "factor": 1.0, "interpretation": "min_total",
                    "repeats": 5, "of": 5, "status": "assumed"},
                   {"meaning": "Temperatur", "unit": "°C", "ds": 0x25, "cmd": 0x2009, "byte": 2, "encoding": "u16be", "factor": 0.1, "interpretation": "number",
                    "repeats": 5, "of": 5, "status": "assumed"}],
        "actions_recorded": {"door_open": 3}}


def test_valid_contribution_has_no_problems():
    assert contribution.validate(GOOD) == []


@pytest.mark.parametrize("change,expect", [
    (lambda d: d.update(protocol="nope"), "protocol"), (lambda d: d.update(format=2), "format"), (lambda d: d.update(extra=1), "unknown field 'extra'"),
    (lambda d: d["findings"][0].update(status="confirmed!"), "status"), (lambda d: d["findings"][0].update(ds=300), "ds out of range"),
    (lambda d: d["findings"][0].update(host="x"), "unknown field 'host'"), (lambda d: d["findings"][0].update(cmd="a"), "cmd must be"),
    (lambda d: d["findings"][0].update(meaning=""), "meaning"), (lambda d: d["values"][0].update(encoding="f32"), "encoding"),
    (lambda d: d.update(findings=[], values=[]), "no findings"),
    (lambda d: d["findings"][0].update(meaning="in " + ".".join(["10", "1", "2", "3"])), "IP address"),
    (lambda d: d["findings"][0].update(meaning=":".join(["aa"] * 6)), "MAC address"),
    (lambda d: d["findings"][0].update(meaning="A" * 44), "key-like"),
    (lambda d: d["findings"][0].update(meaning="dryer.lan"), "host name"),
    (lambda d: d["findings"][0].update(meaning="at 1800100000"), "timestamp"),
])
def test_validation_catches_shape_and_private_data(change, expect):
    import copy
    d = copy.deepcopy(GOOD); change(d)
    assert any(expect in p for p in contribution.validate(d)), contribution.validate(d)


def test_non_objects_are_rejected():
    assert contribution.validate([]) and contribution.validate("x") and contribution.validate(None)


def test_spec_snippet_is_valid_yaml_in_the_spec_format():
    text = contribution.to_spec_snippet(GOOD)
    assert text.startswith("# Suggested by the companion")
    cmds = yaml.safe_load(text)
    assert [c["key"] for c in cmds] == ["17/1010", "17/1011", "25/2008", "25/2009"]
    door_cmd = cmds[0]
    assert door_cmd["status"] == "assumed" and "Neff S413K60S0E" in door_cmd["evidence"] and "3 of 3" in door_cmd["evidence"]
    assert door_cmd["fields"] == [{"byte": 2, "bit": 0, "name": "tuer_geoeffnet", "label": "Tür geöffnet", "status": "assumed"}]
    assert cmds[1]["fields"][0]["kind"] == "u8" and cmds[2]["fields"] == [{"byte": 0, "kind": "u8", "name": "restzeit", "label": "Restzeit", "status": "assumed", "unit": "min"}]
    assert cmds[3]["fields"][0] == {"byte": 2, "kind": "u16", "name": "temperatur", "label": "Temperatur", "status": "assumed", "unit": "°C", "scale": 0.1}


def merged_spec(monkeypatch, commands):
    """The real bshdbus spec plus the given entries, served to the real decoder."""
    import copy
    merged = copy.deepcopy(spec.load_spec("bshdbus"))
    merged["commands"] = [*merged["commands"], *commands]
    merged["_index"] = {c["key"]: c for c in merged["commands"]}
    monkeypatch.setattr(spec, "load_spec", lambda protocol: merged)


def test_snippet_entries_decode_through_the_real_decoder(monkeypatch):
    merged_spec(monkeypatch, yaml.safe_load(contribution.to_spec_snippet(GOOD)))
    out = spec.decode("bshdbus", 0x25, 0x2009, bytes([0, 0, 0x01, 0x2C]))
    assert out["values"] == {"temperatur": 30.0} and out["status"] == "assumed"
    assert spec.decode("bshdbus", 0x17, 0x1010, bytes([0, 0, 1]))["values"] == {"tuer_geoeffnet": True}
    assert spec.decode("bshdbus", 0x17, 0x1010, bytes([0, 0, 0]))["values"] == {"tuer_geoeffnet": False}
    assert spec.decode("bshdbus", 0x25, 0x2008, bytes([105]))["values"] == {"restzeit": 105}


def test_scale_and_little_endian_words_in_the_decoder(monkeypatch):
    entry = {"key": "25/2f09", "name": "t", "title": "t", "status": "assumed", "evidence": "e",
             "fields": [{"byte": 0, "kind": "u16le", "name": "le", "label": "le", "status": "assumed"},
                        {"byte": 0, "kind": "u16", "name": "be", "label": "be", "status": "assumed", "scale": 0.1}]}
    merged_spec(monkeypatch, [entry])
    assert spec.decode("bshdbus", 0x25, 0x2F09, bytes([0x01, 0x2C]))["values"] == {"le": 0x2C01, "be": 30.0}


def test_every_file_in_contributions_passes_the_check():
    root = Path(__file__).resolve().parent.parent / "contributions"
    for f in root.glob("*/*.json"):
        assert contribution.validate(json.loads(f.read_text(encoding="utf-8"))) == [], f


def test_cli_validates_and_suggests(tmp_path, capsys):
    good, bad = tmp_path / "g.json", tmp_path / "b.json"
    good.write_text(json.dumps(GOOD), encoding="utf-8")
    bad.write_text(json.dumps({**GOOD, "protocol": "x"}), encoding="utf-8")
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "validate-contribution", str(good)]) == 0 and "OK" in capsys.readouterr().out
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "validate-contribution", str(good), str(bad)]) == 1 and "protocol" in capsys.readouterr().out
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "suggest-spec", str(good)]) == 0 and "17/1010" in capsys.readouterr().out
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "suggest-spec", str(bad)]) == 1


@pytest.fixture
def client(tmp_path):
    store = Store(tmp_path / "c.sqlite")
    store.source("dw", "bshdbus")
    put_frames(store, "dw", series(door))
    for m in door_markers():
        store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "secret.lan", 6053, None)
    yield TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456"), store), follow_redirects=False)
    store.close()


def test_export_from_the_app_always_passes_the_check_and_gives_a_suggestion(client):
    token = login(client)
    client.post("/s/dw/learned", data={"csrf": token, "group": "door_open", "ds": 0x17, "cmd": 0x1010, "pos": 2, "meaning": "Door is open"})
    doc = client.get("/s/dw/contribution.json").json()
    assert contribution.validate(doc) == [] and doc["values"] == [] and doc["findings"][0]["meaning"] == "Door is open"
    r = client.get("/s/dw/contribution.yaml")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-type"].startswith("text/plain")
    cmds = yaml.safe_load(r.text)
    assert cmds[0]["key"] == "17/1010" and cmds[0]["fields"][0]["bit"] == 0 and "secret" not in r.text
    assert client.get("/s/nope/contribution.yaml").status_code == 404
    assert re.search(r'href="/s/dw/contribution.yaml"', client.get("/s/dw/learn").text)
