"""Device catalogue for the 'new device' dialog: type, manufacturer, model and the protocol that decodes it."""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from . import protocols


@lru_cache(maxsize=None)
def _base() -> dict[str, Any]:
    return yaml.safe_load(resources.files("device_bus_analyzer").joinpath("catalog.yaml").read_text(encoding="utf-8"))


def validate_catalog() -> list[str]:
    cat, problems = _base(), []
    for mid, m in cat.get("manufacturers", {}).items():
        if m.get("protocol") not in protocols.PROTOCOLS:
            problems.append(f"manufacturer {mid}: unknown protocol {m.get('protocol')!r}")
        for t in m.get("types", []):
            if t not in cat.get("types", {}):
                problems.append(f"manufacturer {mid}: unknown type {t!r}")
        if not m.get("name"):
            problems.append(f"manufacturer {mid}: missing name")
    return problems


def build(used: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Catalogue as the dialog needs it: the shipped suggestions plus every value already used by a stored device,
    so that a manufacturer or model typed once is offered again. Result is JSON-serialisable."""
    cat = _base()
    types = {k: dict(v) for k, v in cat.get("types", {}).items()}
    mans: dict[str, dict[str, Any]] = {}
    for mid, m in cat.get("manufacturers", {}).items():
        mans[m["name"]] = {"name": m["name"], "protocol": m["protocol"], "types": list(m.get("types", [])),
                           "models": list(m.get("models", []))}
    for u in used or []:
        t, man, mod, proto = u.get("type"), u.get("manufacturer"), u.get("model"), u.get("protocol")
        if t and t not in types:
            types[t] = {"de": t, "en": t}
        if not man:
            continue
        e = mans.setdefault(man, {"name": man, "protocol": proto, "types": [], "models": []})
        if t and t not in e["types"]:
            e["types"].append(t)
        if mod and mod not in e["models"]:
            e["models"].append(mod)
    return {"types": types, "manufacturers": list(mans.values()), "protocols": sorted(protocols.PROTOCOLS)}
