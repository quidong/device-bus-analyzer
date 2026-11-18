"""Spec-driven decoding: turns (destination, command, data) into named, status-tagged values."""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

STATUS = ("confirmed", "assumed", "unknown")


@lru_cache(maxsize=None)
def load_spec(protocol: str) -> dict[str, Any]:
    text = resources.files("device_bus_analyzer").joinpath("spec", f"{protocol}.yaml").read_text(encoding="utf-8")
    spec = yaml.safe_load(text)
    spec["_index"] = {c["key"]: c for c in spec.get("commands", [])}
    return spec


def lookup(spec: dict[str, Any], ds: int, cmd: int) -> dict[str, Any] | None:
    idx = spec["_index"]
    return idx.get(f"{ds:02x}/{cmd:04x}") or idx.get(f"*/{cmd:04x}")


def decode(protocol: str, ds: int, cmd: int, data: bytes) -> dict[str, Any]:
    """Return {'key', 'name', 'title', 'status', 'values': {...}, 'notes': [...]}; unknown commands get status 'unknown'."""
    spec = load_spec(protocol)
    key = f"{ds:02x}/{cmd:04x}"
    entry = lookup(spec, ds, cmd)
    if entry is None:
        return {"key": key, "name": None, "title": None, "status": "unknown", "values": {}, "notes": ["not in spec"]}
    values: dict[str, Any] = {}
    notes: list[str] = []
    for f in entry.get("fields", []):
        b = f["byte"]
        if b >= len(data):
            notes.append(f"{f['name']}: data too short ({len(data)} bytes)")
            continue
        if "bit" in f:
            values[f["name"]] = bool(data[b] >> f["bit"] & 1)
        elif f.get("kind") == "enum":
            label = spec.get("enums", {}).get(f["enum"], {}).get(f"0x{data[b]:02x}")
            values[f["name"]] = label if label is not None else f"0x{data[b]:02x}"
        else:
            values[f["name"]] = data[b]
    return {"key": key, "name": entry["name"], "title": entry["title"], "status": entry["status"],
            "values": values, "notes": notes}


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
    return problems
