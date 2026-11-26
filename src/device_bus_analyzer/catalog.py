"""Device catalogue for the 'new device' dialog: type, manufacturer (brand), model, the decoder protocol and the firmware to flash."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from . import i18n, knowledge, protocols


@lru_cache(maxsize=None)
def _base() -> dict[str, Any]:
    return yaml.safe_load(knowledge.read("catalog.yaml"))


def _fw_text(name: str) -> str:
    return knowledge.read(f"firmware/{name}")


def _fw_exists(name: str) -> bool:
    try:
        _fw_text(name)
        return True
    except (OSError, FileNotFoundError):
        return False


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
            if "/" in f or not _fw_exists(f):
                problems.append(f"firmware {proto}: file {f!r} missing")
        for lang in i18n.LANGS:
            if not prof.get("note", {}).get(lang):
                problems.append(f"firmware {proto}: note.{lang} missing")
    for ctype, ctl in cat.get("controls", {}).items():
        ids = {e.get("id") for e in ctl.get("events", [])}
        for e in ctl.get("events", []):
            if not all(e.get(x) for x in i18n.LANGS):
                problems.append(f"controls {ctype}: event {e.get('id')!r} needs de and en")
            if e.get("pair") and e["pair"] not in ids:
                problems.append(f"controls {ctype}: event {e['id']!r} pairs with unknown {e['pair']!r}")
        for g in ctl.get("guided", []):
            if not (all(g.get(x) for x in i18n.LANGS) and g.get("steps")) or int(g.get("repeat", 1)) < 1:
                problems.append(f"controls {ctype}: guided {g.get('id')!r} incomplete")
            for x in (g.get("rest", 0), *(st.get("hold", 0) for st in g.get("steps", []))):
                if not isinstance(x, int) or not 0 <= x <= 600:
                    problems.append(f"controls {ctype}: guided {g.get('id')!r} has a bad rest/hold time {x!r}")
            for st in g.get("steps", []):
                if st.get("event") not in ids or not all(st.get(x) for x in i18n.LANGS):
                    problems.append(f"controls {ctype}: guided {g.get('id')!r} has a bad step {st.get('event')!r}")
    if "generic" not in cat.get("controls", {}):
        problems.append("controls: 'generic' is missing")
    return problems


def controls(dev_type: str | None, lang: str = "en") -> dict[str, Any]:
    """Companion buttons and guided checks for a device type, in one language. Unknown types get the generic set."""
    all_ctl = _base().get("controls", {})
    ctl = all_ctl.get(dev_type or "", all_ctl.get("generic", {}))
    pick = lambda d: d.get(lang) or d.get("en") or ""                           # noqa: E731
    events = [{"id": e["id"], "label": pick(e), "pair": e.get("pair"), "ask": bool(e.get("ask")), "by_note": bool(e.get("by_note"))}
              for e in ctl.get("events", [])]
    guided = [{"id": g["id"], "label": pick(g), "repeat": int(g.get("repeat", 1)), "rest": int(g.get("rest", 0)),
               "steps": [{"event": s["event"], "text": pick(s), "ask": bool(s.get("ask")), "hold": int(s.get("hold", 0))} for s in g["steps"]]}
              for g in ctl.get("guided", [])]
    return {"events": events, "guided": guided}


def event_rules(dev_type: str | None) -> dict[str, dict[str, Any]]:
    """{event id: {'pair', 'by_note'}} for the analysis."""
    return {e["id"]: {"pair": e["pair"], "by_note": e["by_note"]} for e in controls(dev_type)["events"]}


def build(used: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Catalogue as the dialog needs it: the shipped suggestions plus every value already used by a stored device or
    remembered from an earlier save, so that a manufacturer or model typed once is offered again (also after the device
    is deleted). Every manufacturer is offered for every type; ``model_types`` says for which types a model is known
    (empty: any). Result is JSON-serialisable."""
    cat = _base()
    types = {k: dict(v) for k, v in cat.get("types", {}).items()}
    mans: dict[str, dict[str, Any]] = {}
    for m in cat.get("manufacturers", {}).values():
        mtypes = list(m.get("types", []))
        mans[m["name"]] = {"name": m["name"], "protocol": m["protocol"], "types": mtypes, "models": list(m.get("models", [])),
                           # a shipped model belongs to the manufacturer's type when it makes only one kind of device
                           "model_types": {x: (mtypes[:1] if len(mtypes) == 1 else []) for x in m.get("models", [])}, "known": True}
    for u in used or []:
        t, man, mod, proto = u.get("type"), u.get("manufacturer"), u.get("model"), u.get("protocol")
        if t and t not in types:
            types[t] = {x: t for x in i18n.LANGS}
        if not man:
            continue
        e = mans.setdefault(man, {"name": man, "protocol": proto, "types": [], "models": [], "model_types": {}, "known": False})
        if t and t not in e["types"]:
            e["types"].append(t)
        if mod and mod not in e["models"]:
            e["models"].append(mod)
        if mod:
            mt = e["model_types"].setdefault(mod, [])
            if t and t not in mt:
                mt.append(t)
    return {"types": types, "manufacturers": list(mans.values()), "protocols": sorted(protocols.PROTOCOLS)}


def firmware_profile(protocol: str, lang: str = "en") -> dict[str, Any] | None:
    """Recommended ESPHome files for a protocol: {'files': [{'name', 'text'}], 'note'} or None if there is none."""
    prof = _base().get("firmware", {}).get(protocol)
    if not prof:
        return None
    files = [{"name": f, "text": _fw_text(f), "kind": "yaml" if f.endswith((".yaml", ".yml")) else "code"}
             for f in prof.get("files", [])]
    note = prof.get("note", {})
    return {"files": files, "note": note.get(lang) or note.get("en") or ""}


def firmware_file(name: str) -> str | None:
    return _fw_text(name) if name in firmware_names() else None
