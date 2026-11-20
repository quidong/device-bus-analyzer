"""What may leave an installation: accepted findings (no telegrams, times, hosts or keys), a check for it, and a spec suggestion.

The export is what a person attaches to an issue or a pull request. ``validate`` is what the CI runs on every file in
``contributions/``; ``to_spec_snippet`` turns it into entries in the format of ``spec/<protocol>.yaml``.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

import yaml

FORMAT = 1
ENC_KIND = {"u8": "u8", "u16be": "u16", "u16le": "u16le"}
TOP_KEYS = {"format", "protocol", "type", "manufacturer", "model", "findings", "values", "actions_recorded"}
FINDING_KEYS = {"meaning", "action", "ds", "cmd", "byte", "from", "to", "mask", "repeats", "of", "status"}   # mask: compared bits (absent = all)
VALUE_KEYS = {"meaning", "unit", "ds", "cmd", "byte", "encoding", "factor", "interpretation", "repeats", "of", "status"}
STATUS = ("assumed", "confirmed")
PRIVATE = [(re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "an IP address"), (re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b"), "a MAC address"),
           (re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"), "a long key-like string"), (re.compile(r"\b[\w-]+\.(?:lan|local|home|fritz\.box)\b", re.I), "a host name"),
           (re.compile(r"\b1[6-9]\d{8}\b"), "a timestamp")]


def build_export(store, source: str, protocol: str, device: dict | None) -> dict[str, Any]:
    d = device or {}
    kinds = Counter(m["kind"] for m in store.markers(source, limit=5000))
    return {
        "format": FORMAT, "protocol": protocol, "type": d.get("type"), "manufacturer": d.get("manufacturer"), "model": d.get("model"),
        "findings": [{"meaning": f["meaning"], "action": f["kind"], "ds": f["ds"], "cmd": f["cmd"], "byte": f["pos"], "from": f["from_val"],
                      "to": f["to_val"], **({"mask": f["mask"]} if f.get("mask") is not None else {}), "repeats": f["hits"], "of": f["n"],
                      "status": f["status"]} for f in store.learned(source)],
        "values": [{"meaning": v["meaning"], "unit": v["unit"], "ds": v["ds"], "cmd": v["cmd"], "byte": v["pos"], "encoding": v["enc"],
                    "factor": v["factor"], "interpretation": v["interp"], "repeats": v["hits"], "of": v["n"], "status": v["status"]}
                   for v in store.learned_values(source)],
        "actions_recorded": dict(kinds)}


def validate(doc: Any, known_protocols: tuple[str, ...] = ("bshdbus", "macs")) -> list[str]:
    """Problems in a contribution file; empty = acceptable. Checks the shape and that nothing private slipped in."""
    if not isinstance(doc, dict):
        return ["the file must contain a JSON object"]
    problems = [f"unknown field {k!r}" for k in doc if k not in TOP_KEYS]
    if doc.get("format") != FORMAT:
        problems.append(f"format must be {FORMAT}")
    if doc.get("protocol") not in known_protocols:
        problems.append(f"protocol must be one of {', '.join(known_protocols)}")
    for k in ("type", "manufacturer", "model"):
        if doc.get(k) is not None and not isinstance(doc[k], str):
            problems.append(f"{k} must be text")
    if not (doc.get("findings") or doc.get("values")):
        problems.append("no findings and no values")
    for kind, keys, rows in (("finding", FINDING_KEYS, doc.get("findings") or []), ("value", VALUE_KEYS, doc.get("values") or [])):
        for i, r in enumerate(rows):
            where = f"{kind} {i + 1}"
            if not isinstance(r, dict):
                problems.append(f"{where}: must be an object"); continue
            problems += [f"{where}: unknown field {k!r}" for k in r if k not in keys]
            for k in ("ds", "cmd", "byte", "repeats", "of"):
                if not isinstance(r.get(k), int) or isinstance(r.get(k), bool):
                    problems.append(f"{where}: {k} must be a whole number")
            if isinstance(r.get("ds"), int) and not 0 <= r["ds"] <= 0xFF:
                problems.append(f"{where}: ds out of range")
            if isinstance(r.get("cmd"), int) and not 0 <= r["cmd"] <= 0xFFFF:
                problems.append(f"{where}: cmd out of range")
            if kind == "finding" and r.get("mask") is not None and (not isinstance(r["mask"], int) or isinstance(r["mask"], bool) or not 1 <= r["mask"] <= 255):
                problems.append(f"{where}: mask must be 1..255")
            if r.get("status") not in STATUS:
                problems.append(f"{where}: status must be assumed or confirmed")
            if not isinstance(r.get("meaning"), str) or not r["meaning"].strip():
                problems.append(f"{where}: meaning is missing")
            if kind == "value" and r.get("encoding") not in ENC_KIND:
                problems.append(f"{where}: unknown encoding")
    text = json.dumps(doc, ensure_ascii=False)
    for rx, what in PRIVATE:
        if rx.search(text):
            problems.append(f"looks like it contains {what}")
    return problems


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("_")
    return s[:40] or "field"


def to_spec_snippet(doc: dict[str, Any]) -> str:
    """Entries for ``commands:`` of ``spec/<protocol>.yaml``. Always 'assumed': a maintainer confirms once several people agree."""
    who = " ".join(x for x in (doc.get("manufacturer"), doc.get("model")) if x) or "unknown model"
    by_cmd: dict[tuple[int, int], dict[str, list]] = {}
    for f in doc.get("findings", []):
        by_cmd.setdefault((f["ds"], f["cmd"]), {"fields": [], "notes": []})
    for v in doc.get("values", []):
        by_cmd.setdefault((v["ds"], v["cmd"]), {"fields": [], "notes": []})
    for f in doc.get("findings", []):
        slot = by_cmd[(f["ds"], f["cmd"])]
        a, b = f["from"], f["to"]
        gained = (a ^ b) & b if isinstance(a, int) and isinstance(b, int) else 0
        single = isinstance(a, int) and isinstance(b, int) and bin(a ^ b).count("1") == 1
        note = f"byte {f['byte']} {a:02x} -> {b:02x} for '{f['meaning']}' ({f['repeats']} of {f['of']} repeats)"
        slot["notes"].append(note)
        if single and gained:                                   # a bit that turned on: a flag field
            name = _slug(f["meaning"])
            if not any(x.get("byte") == f["byte"] and x.get("bit") == gained.bit_length() - 1 for x in slot["fields"]):
                slot["fields"].append({"byte": f["byte"], "bit": gained.bit_length() - 1, "name": name, "label": f["meaning"], "status": "assumed"})
        elif not single and not any(x.get("byte") == f["byte"] and "bit" not in x for x in slot["fields"]):
            slot["fields"].append({"byte": f["byte"], "kind": "u8", "name": f"byte{f['byte']}", "label": f"Byte {f['byte']} ({f['meaning']} = {b:02x})", "status": "assumed"})
    for v in doc.get("values", []):
        field: dict[str, Any] = {"byte": v["byte"], "kind": ENC_KIND[v["encoding"]], "name": _slug(v["meaning"]), "label": v["meaning"], "status": "assumed"}
        if v.get("unit"):
            field["unit"] = v["unit"]
        if v.get("factor") not in (None, 1, 1.0):
            field["scale"] = v["factor"]
        slot = by_cmd[(v["ds"], v["cmd"])]
        slot["fields"].append(field)
        slot["notes"].append(f"byte {v['byte']} ({v['encoding']}) follows the display value '{v['meaning']}' ({v['repeats']} of {v['of']} readings)")
    commands = []
    for (ds, cmd), slot in sorted(by_cmd.items()):
        commands.append({"key": f"{ds:02x}/{cmd:04x}", "name": f"learned_{ds:02x}_{cmd:04x}", "title": "Learned in companion mode", "status": "assumed",
                         "evidence": f"{who}: " + "; ".join(slot["notes"]), "fields": slot["fields"]})
    head = f"# Suggested by the companion ({doc.get('protocol')}, {who}). Review, merge into commands: of spec/{doc.get('protocol')}.yaml and run `dba validate-spec`.\n"
    return head + yaml.safe_dump(commands, sort_keys=False, allow_unicode=True, width=1000)
