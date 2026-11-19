"""Device catalogue for the 'new device' dialog: type, manufacturer (brand), model, the decoder protocol and the firmware to flash."""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from . import protocols


@lru_cache(maxsize=None)
def _base() -> dict[str, Any]:
    return yaml.safe_load(resources.files("device_bus_analyzer").joinpath("catalog.yaml").read_text(encoding="utf-8"))


def _fw_dir():
    return resources.files("device_bus_analyzer").joinpath("firmware")


def firmware_names() -> set[str]:
    """Every file a firmware profile may serve. Anything else is refused: no path ever comes from a request."""
    return {f for p in _base().get("firmware", {}).values() for f in p.get("files", [])}


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
        if m.get("protocol") not in cat.get("firmware", {}):
            problems.append(f"manufacturer {mid}: no firmware profile for protocol {m.get('protocol')!r}")
    for proto, prof in cat.get("firmware", {}).items():
        for f in prof.get("files", []):
            if "/" in f or not _fw_dir().joinpath(f).is_file():
                problems.append(f"firmware {proto}: file {f!r} missing")
        for lang in ("de", "en"):
            if not prof.get("note", {}).get(lang):
                problems.append(f"firmware {proto}: note.{lang} missing")
    return problems


def build(used: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Catalogue as the dialog needs it: the shipped suggestions plus every value already used by a stored device,
    so that a manufacturer or model typed once is offered again. Result is JSON-serialisable."""
    cat = _base()
    types = {k: dict(v) for k, v in cat.get("types", {}).items()}
    mans: dict[str, dict[str, Any]] = {}
    for m in cat.get("manufacturers", {}).values():
        mans[m["name"]] = {"name": m["name"], "protocol": m["protocol"], "types": list(m.get("types", [])),
                           "models": list(m.get("models", [])), "known": True}
    for u in used or []:
        t, man, mod, proto = u.get("type"), u.get("manufacturer"), u.get("model"), u.get("protocol")
        if t and t not in types:
            types[t] = {"de": t, "en": t}
        if not man:
            continue
        e = mans.setdefault(man, {"name": man, "protocol": proto, "types": [], "models": [], "known": False})
        if t and t not in e["types"]:
            e["types"].append(t)
        if mod and mod not in e["models"]:
            e["models"].append(mod)
    return {"types": types, "manufacturers": list(mans.values()), "protocols": sorted(protocols.PROTOCOLS)}


def firmware_profile(protocol: str, lang: str = "en") -> dict[str, Any] | None:
    """Recommended ESPHome files for a protocol: {'files': [{'name', 'text'}], 'note'} or None if there is none."""
    prof = _base().get("firmware", {}).get(protocol)
    if not prof:
        return None
    files = [{"name": f, "text": _fw_dir().joinpath(f).read_text(encoding="utf-8"), "kind": "yaml" if f.endswith((".yaml", ".yml")) else "code"}
             for f in prof.get("files", [])]
    note = prof.get("note", {})
    return {"files": files, "note": note.get(lang) or note.get("en") or ""}


def firmware_file(name: str) -> str | None:
    return _fw_dir().joinpath(name).read_text(encoding="utf-8") if name in firmware_names() else None
