"""Current values of everything the person taught the app, as JSON for Home Assistant, and the YAML to read it there.

The analyzer decodes on the server (the firmware only streams raw telegrams), so Home Assistant reads the decoded state with a
``rest`` integration and the API token. Nothing here sends anything to the appliance.
"""
from __future__ import annotations

import json
import time
from typing import Any

from .contribution import _slug
from .learned import decode_value


def _unique(key: str, used: set[str]) -> str:
    k, i = key, 2
    while k in used:
        k, i = f"{key}_{i}", i + 1
    used.add(k)
    return k


def state_fields(store, source: str, now: float | None = None) -> list[dict[str, Any]]:
    now = time.time() if now is None else now
    groups: dict[tuple[int, int, int], dict[int, str]] = {}
    for f in store.learned(source):
        if f["pos"] is not None and f["pos"] >= 0 and f["to_val"] is not None:
            groups.setdefault((f["ds"], f["cmd"], f["pos"]), {})[f["to_val"]] = f["meaning"]
    used: set[str] = set()
    out: list[dict[str, Any]] = []
    for (ds, cmd, pos), mapping in sorted(groups.items()):
        last = store.latest_payload(source, ds, cmd)
        raw = last[1][pos] if last and pos < len(last[1]) else None
        out.append({"key": _unique(_slug(next(iter(mapping.values()))), used), "label": next(iter(mapping.values())), "kind": "state",
                    "raw": raw, "value": raw, "text": mapping.get(raw), "unit": None, "on_values": sorted(mapping),
                    "ts": last[0] if last else None, "age_s": round(now - last[0], 1) if last else None})
    for v in store.learned_values(source):
        last = store.latest_payload(source, v["ds"], v["cmd"])
        x = decode_value(v["enc"], v["pos"], v["factor"], last[1]) if last else None
        out.append({"key": _unique(_slug(v["meaning"]), used), "label": v["meaning"], "kind": "value", "raw": None,
                    "value": None if x is None else round(x, 3), "text": None, "unit": v["unit"], "on_values": [],
                    "ts": last[0] if last else None, "age_s": round(now - last[0], 1) if last else None})
    return out


def render_yaml(source: str, base_url: str, fields: list[dict[str, Any]]) -> str:
    q = json.dumps                                   # a JSON string is a valid YAML double-quoted string
    pick = "{% set f = value_json.fields | selectattr('key','eq','KEY') | list %}"
    head = [f"# configuration.yaml: Device Bus Analyzer, {source}",
            "# secrets.yaml:        dba_bearer: \"Bearer <your API token>\"",
            "rest:",
            f"  - resource: {q(base_url.rstrip('/') + '/api/' + source + '/state')}",
            "    scan_interval: 30",
            "    headers:",
            "      Authorization: !secret dba_bearer"]
    sensors, binaries = [], []
    for f in fields:
        k = f["key"]
        uid = q(f"dba_{source}_{k}")
        if f["kind"] == "value":
            tpl = pick.replace("KEY", k) + "{{ f[0].value if f else none }}"
            s = [f"      - name: {q(source + ' ' + f['label'])}", f"        unique_id: {uid}", f"        value_template: {q(tpl)}"]
            if f.get("unit"):
                s.append(f"        unit_of_measurement: {q(f['unit'])}")
            sensors.append("\n".join(s))
        else:
            tpl = pick.replace("KEY", k) + "{{ f[0].text if f else none }}"
            sensors.append("\n".join([f"      - name: {q(source + ' ' + f['label'])}", f"        unique_id: {uid}", f"        value_template: {q(tpl)}"]))
            if len(f["on_values"]) == 1:
                on = pick.replace("KEY", k) + "{{ f[0].raw == %d if f else none }}" % f["on_values"][0]
                binaries.append("\n".join([f"      - name: {q(source + ' ' + f['label'])}", f"        unique_id: {q('dba_' + source + '_' + k + '_on')}",
                                           f"        value_template: {q(on)}"]))
    body = ["    sensor:", *sensors] if sensors else []
    if binaries:
        body += ["    binary_sensor:", *binaries]
    return "\n".join(head + body) + "\n"
