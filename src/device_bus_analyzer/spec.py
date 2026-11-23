"""Spec-driven decoding: turns (destination, command, data) into named, status-tagged values."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from . import knowledge

STATUS = ("confirmed", "assumed", "unknown")


@lru_cache(maxsize=None)
def load_spec(protocol: str) -> dict[str, Any]:
    text = knowledge.read(f"spec/{protocol}.yaml")
    spec = yaml.safe_load(text)
    spec["_index"] = {c["key"]: c for c in spec.get("commands", [])}
    return spec


def lookup(spec: dict[str, Any], ds: int, cmd: int) -> dict[str, Any] | None:
    idx = spec["_index"]
    return idx.get(f"{ds:02x}/{cmd:04x}") or idx.get(f"*/{cmd:04x}")


def _unknown(why: str) -> dict[str, Any]:
    return {"value": None, "status": "unknown", "evidence": why}


def node_info(spec: dict[str, Any], ds: int) -> dict[str, Any]:
    """Sender/receiver derived from the destination. Always carries a status; 'unknown' if the spec has no entry."""
    nodes = spec.get("nodes", {})
    entry = nodes.get(f"{ds:02x}") or nodes.get(f"{ds >> 4:x}x")
    if not entry:
        return {"sender": _unknown("no node entry in the spec"), "receiver": _unknown("no node entry in the spec")}
    st = entry.get("status", "assumed")
    return {"sender": {"value": entry.get("sender"), "status": st if entry.get("sender") else "unknown", "evidence": entry.get("evidence", "")},
            "receiver": {"value": entry.get("receiver"), "status": st if entry.get("receiver") else "unknown", "evidence": entry.get("evidence", "")}}


def device_info(spec: dict[str, Any], ds: int, cmd: int) -> dict[str, Any]:
    """Buses whose frames carry source AND destination (MACS): ``cmd`` high byte = source address.

    The addresses are read from the wire (always true); what a device *is* comes from ``devices`` in the spec
    and keeps that entry's status.
    """
    devs = spec.get("devices", {})

    def one(addr: int, role: str) -> dict[str, Any]:
        e = devs.get(f"{addr:02x}")
        if not e:
            return _unknown(f"{role} address 0x{addr:02x} is not in the spec")
        return {"value": e["name"], "status": e.get("status", "assumed"), "evidence": e.get("evidence", "")}

    src = cmd >> 8
    return {"sender": one(src, "source"), "receiver": one(ds, "destination"),
            "dest_node": {**one(ds, "destination"), "value": ds, "name": (devs.get(f"{ds:02x}") or {}).get("name")},
            "subsystem": {"value": None, "name": None, "status": "unknown", "evidence": "no subsystem nibble on this bus"}}


def dest_info(spec: dict[str, Any], ds: int) -> dict[str, Any]:
    """Split the DS byte: high nibble = destination node, low nibble = subsystem (per hn/bsh-home-appliances)."""
    node, sub = ds >> 4, ds & 0xF
    ne = spec.get("node_addresses", {}).get(f"{node:x}")
    se = spec.get("subsystems", {}).get(f"{sub:x}")
    return {
        "dest_node": {"value": node, "name": ne["name"] if ne else None,
                      "status": ne.get("status", "assumed") if ne else "unknown",
                      "evidence": ne.get("evidence", "") if ne else "node address not in the spec"},
        "subsystem": {"value": sub, "name": se["name"] if se else None,
                      "status": se.get("status", "assumed") if se else "unknown",
                      "evidence": se.get("evidence", "") if se else "subsystem not in the spec"},
    }


def ack_info(spec: dict[str, Any], ack: int | None) -> dict[str, Any] | None:
    """Who acknowledged (high nibble of the ACK byte). None if the frame had no ACK."""
    if ack is None:
        return None
    entry = spec.get("acks", {}).get(f"{ack >> 4:x}")
    if not entry:
        return {"value": None, "status": "unknown", "evidence": f"ACK {ack:02X}: node class not in the spec"}
    return {"value": entry["node"], "status": entry.get("status", "assumed"), "evidence": entry.get("evidence", "")}


def decode(protocol: str, ds: int, cmd: int, data: bytes, ack: int | None = None) -> dict[str, Any]:
    """Decode one telegram.

    Result keys: key, name, title, status (of the command), values {name: value}, fields [{name,label,value,unit,status}]
    with a status per value, sender / receiver / acked_by ({value, status, evidence}; value None = unknown), notes.
    """
    spec = load_spec(protocol)
    key = f"{ds:02x}/{cmd:04x}"
    if spec.get("source_in_cmd"):
        base = {"key": key, **device_info(spec, ds, cmd), "acked_by": ack_info(spec, ack)}
    else:
        base = {"key": key, **node_info(spec, ds), "acked_by": ack_info(spec, ack), **dest_info(spec, ds)}
    entry = lookup(spec, ds, cmd)
    if entry is None:
        return {**base, "name": None, "title": None, "status": "unknown", "values": {}, "fields": [], "notes": ["not in spec"]}
    values: dict[str, Any] = {}
    fields: list[dict[str, Any]] = []
    notes: list[str] = []
    for f in entry.get("fields", []):
        b = f["byte"]
        when = f.get("when")      # field only exists in one layout of the message: {byte: n, value: v}
        if when is not None and not (len(data) > when["byte"] and data[when["byte"]] == when["value"]):
            continue
        if b >= len(data):
            notes.append(f"{f['name']}: data too short ({len(data)} bytes)")
            continue
        if f.get("kind") == "ascii":
            n = int(f.get("length", 1))
            if b + n > len(data):
                notes.append(f"{f['name']}: data too short ({len(data)} bytes)")
                continue
            v = bytes(data[b:b + n]).decode("ascii", errors="replace")
            values[f["name"]] = v
            fields.append({"name": f["name"], "label": f.get("label", f["name"]), "value": v, "unit": f.get("unit"),
                           "status": f.get("status", entry["status"])})
            continue
        if f.get("kind") in ("u16", "u16le", "s16"):
            if b + 1 >= len(data):
                notes.append(f"{f['name']}: data too short ({len(data)} bytes)")
                continue
            v: Any = data[b] << 8 | data[b + 1] if f["kind"] != "u16le" else data[b + 1] << 8 | data[b]
            if f.get("mask") is not None:
                v &= int(f["mask"])
            if f["kind"] == "s16" and v >= 0x8000:
                v -= 0x10000
        elif "bit" in f:
            v = bool(data[b] >> f["bit"] & 1)
        elif f.get("kind") == "enum":
            label = spec.get("enums", {}).get(f["enum"], {}).get(f"0x{data[b]:02x}")
            v = label if label is not None else f"0x{data[b]:02x}"
        else:
            v = data[b]
        if f.get("scale") and isinstance(v, (int, float)) and not isinstance(v, bool):
            v = round(v * f["scale"], 3)
        values[f["name"]] = v
        fields.append({"name": f["name"], "label": f.get("label", f["name"]), "value": v, "unit": f.get("unit"),
                       "status": f.get("status", entry["status"])})
    return {**base, "name": entry["name"], "title": entry["title"], "status": entry["status"],
            "values": values, "fields": fields, "notes": notes}


def validate_spec(protocol: str) -> list[str]:
    """Return a list of problems (empty = spec is consistent)."""
    spec = load_spec(protocol)
    problems, seen = [], set()
    for c in spec.get("commands", []):
        for k in ("key", "name", "title", "status", "evidence"):
            if k not in c:
                problems.append(f"{c.get('key', '?')}: missing {k}")
        if c.get("status") not in STATUS:
            problems.append(f"{c.get('key')}: bad status {c.get('status')!r}")
        if c["key"] in seen:
            problems.append(f"{c['key']}: duplicate")
        seen.add(c["key"])
        for f in c.get("fields", []):
            if f.get("status") not in STATUS:
                problems.append(f"{c['key']}.{f.get('name')}: bad status")
            if f.get("kind") == "enum" and f.get("enum") not in spec.get("enums", {}):
                problems.append(f"{c['key']}.{f.get('name')}: unknown enum {f.get('enum')}")
    for k, n in spec.get("devices", {}).items():
        if n.get("status") not in STATUS:
            problems.append(f"device {k}: bad status")
    for k, n in spec.get("nodes", {}).items():
        if n.get("status") not in STATUS:
            problems.append(f"node {k}: bad status")
    for k, n in spec.get("acks", {}).items():
        if n.get("status") not in STATUS:
            problems.append(f"ack {k}: bad status")
    return problems
