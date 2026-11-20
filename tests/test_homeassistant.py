"""Home Assistant output: current state of taught fields and the YAML that reads it."""
import yaml
from test_companion import login  # noqa: F401
from test_learning import client, remaining_series, store  # noqa: F401  (fixtures)

from device_bus_analyzer import homeassistant

H = {"Authorization": "Bearer tok-123456"}


def teach(client, token):
    for group, meaning in (("door_open", "Door is open"),):
        assert client.post("/s/dw/learned", data={"csrf": token, "group": group, "ds": 0x17, "cmd": 0x1010, "pos": 2, "meaning": meaning}).status_code == 303
    assert client.post("/s/dw/values", data={"csrf": token, "ds": 0x25, "cmd": 0x2008, "pos": 0, "enc": "u8", "factor": 1.0, "interp": "min_total",
                                             "meaning": "Remaining time", "unit": "min"}).status_code == 303


def test_state_api_returns_the_newest_taught_values(client, store):
    assert client.get("/api/dw/state").status_code == 401
    assert client.get("/api/dw/state", headers=H).json() == {"source": "dw", "fields": []}          # nothing taught yet
    teach(client, login(client))
    f = {x["key"]: x for x in client.get("/api/dw/state", headers=H).json()["fields"]}
    assert set(f) == {"door_is_open", "remaining_time"}
    door, left = f["door_is_open"], f["remaining_time"]
    assert door["kind"] == "state" and door["raw"] == 0 and door["text"] is None and door["on_values"] == [1]        # door byte is 0 and only "open" is named
    assert left["kind"] == "value" and left["value"] == 105 - 699 // 60 and left["unit"] == "min" and left["age_s"] is not None
    assert client.get("/api/nope/state", headers=H).status_code == 404


def test_yaml_is_valid_home_assistant_rest_configuration(client):
    teach(client, login(client))
    html = client.get("/s/dw/homeassistant?lang=en").text
    assert "Remaining time" in html and 'data-target="ha-yaml"' in html and "dba_bearer" in html
    import html as h
    text = h.unescape(html.split('<pre class="code" id="ha-yaml" tabindex="0"><code>')[1].split("</code>")[0])
    cfg = yaml.safe_load(text.replace("!secret", ""))
    rest = cfg["rest"][0]
    assert rest["resource"].endswith("/api/dw/state") and rest["scan_interval"] == 30
    names = [s["name"] for s in rest["sensor"]]
    assert names == ["dw Door is open", "dw Remaining time"] and rest["sensor"][1]["unit_of_measurement"] == "min"
    assert [b["name"] for b in rest["binary_sensor"]] == ["dw Door is open"]            # one named value: also a binary sensor
    assert "raw == 1" in rest["binary_sensor"][0]["value_template"] and rest["sensor"][0]["unique_id"] == "dba_dw_door_is_open"
    assert len({s["unique_id"] for s in rest["sensor"]}) == 2


def test_page_without_taught_fields_points_to_learning(client):
    login(client)
    html = client.get("/s/dw/homeassistant?lang=en").text
    assert "Nothing taught yet" in html and 'href="/s/dw/learn"' in html and "ha-yaml" not in html


def test_keys_are_unique_and_templates_are_quoted():
    used: set[str] = set()
    assert [homeassistant._unique("a", used) for _ in range(3)] == ["a", "a_2", "a_3"]
    y = homeassistant.render_yaml("x", "http://h:8080/", [{"key": "k", "label": 'Say "hi"', "kind": "value", "unit": "°C", "on_values": []}])
    assert yaml.safe_load(y.replace("!secret", ""))["rest"][0]["sensor"][0]["name"] == 'x Say "hi"'


def test_device_card_links_to_home_assistant_once_something_is_taught(client, store):
    token = login(client)
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", None, None)
    assert 'href="/s/dw/homeassistant"' not in client.get("/devices").text
    teach(client, token)
    assert 'href="/s/dw/homeassistant"' in client.get("/devices").text
