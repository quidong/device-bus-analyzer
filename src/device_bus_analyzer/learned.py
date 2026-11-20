"""Apply what the person accepted in the companion: turn raw bytes into the meaning they gave them.

``states``  (byte -> value -> meaning): "byte 2 = 01" is shown as "Door opened". Only the bits that were compared when the finding was
            made count (``mask``): a flickering bit next to the door bit must not hide the door. A meaning is known for the value the action leads to
            (and for the opposite value when the opposite action was accepted as well).
``values``  (display values): a byte or word that follows a number shown on the appliance (remaining time, temperature).
"""
from __future__ import annotations

from typing import Any

ENCODINGS = ("u8", "u16be", "u16le")


def decode_value(enc: str, pos: int, factor: float, data: bytes) -> float | None:
    """Read a number from the payload; None when the payload is too short."""
    try:
        if enc == "u8":
            raw = data[pos]
        elif enc == "u16be":
            raw = data[pos] << 8 | data[pos + 1]
        elif enc == "u16le":
            raw = data[pos + 1] << 8 | data[pos]
        else:
            return None
    except IndexError:
        return None
    return raw * factor


def number(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def overlay(learned: list[dict], values: list[dict]) -> dict[tuple[int, int], dict[str, Any]]:
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for f in learned:
        if f["pos"] is None or f["pos"] < 0 or f["to_val"] is None:
            continue
        o = out.setdefault((f["ds"], f["cmd"]), {"states": {}, "values": []})
        mask = f.get("mask")
        o["states"].setdefault(f["pos"], {}).setdefault(255 if mask is None else mask, {})[f["to_val"]] = f["meaning"]
    for v in values:
        out.setdefault((v["ds"], v["cmd"]), {"states": {}, "values": []})["values"].append(v)
    return out


def describe(ov: dict[tuple[int, int], dict[str, Any]], ds: int, cmd: int, data: bytes) -> list[str]:
    """What the accepted findings say about one payload, e.g. ['Door opened', 'Remaining time: 105 min']."""
    o = ov.get((ds, cmd))
    if not o:
        return []
    out = []
    for pos, masks in sorted(o["states"].items()):
        for mask, mapping in sorted(masks.items()):
            if pos < len(data) and data[pos] & mask in mapping:
                out.append(mapping[data[pos] & mask])
    for v in o["values"]:
        x = decode_value(v["enc"], v["pos"], v["factor"], data)
        if x is not None:
            out.append(f"{v['meaning']}: {number(x)}" + (f" {v['unit']}" if v.get("unit") else ""))
    return out
