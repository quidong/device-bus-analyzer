"""FastAPI application: GET-only JSON API (/api) and HTML frontend. Nothing here can write to a device."""
from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from importlib import resources
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__, analysis, catalog, i18n, protocols
from .auth import COOKIE, CSRF_COOKIE, Auth
from .config import Settings, validate_device_input
from .spec import load_spec
from .store import Store

PKG = resources.files("device_bus_analyzer")
log = logging.getLogger("dba.web")


def parse_time(v: str | None, tz: ZoneInfo) -> float | None:
    """Accepts epoch seconds or ISO 8601 (naive values are interpreted in the configured timezone)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        pass
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, f"bad time {v!r}") from None
    return (d if d.tzinfo else d.replace(tzinfo=tz)).timestamp()


def parse_hex(v: str | None, digits: int) -> int | None:
    if v is None or v == "":
        return None
    try:
        n = int(v, 16)
    except ValueError:
        raise HTTPException(422, f"bad hex {v!r}") from None
    if not 0 <= n < 16 ** digits:
        raise HTTPException(422, f"hex out of range {v!r}")
    return n


def jsonable(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        if isinstance(r.get("data"), (bytes, bytearray)):
            r["data"] = bytes(r["data"]).hex()
        out.append(r)
    return out


def create_app(settings: Settings, store: Store, start_collectors: bool = False) -> FastAPI:
    auth = Auth(settings)
    tz = ZoneInfo(os.environ.get("DBA_TZ", "Europe/Berlin"))
    tpl = Jinja2Templates(directory=str(PKG.joinpath("templates")))
    from .collector import CollectorManager
    manager = CollectorManager(store)
    created = store.seed_devices(settings.devices)   # former DBA_DEVICES / DBA_KEY_<NAME>: imported once, never overwrites
    if created:
        log.info("devices imported from the environment: %s", ", ".join(created))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_collectors:
            manager.sync()
        yield
        manager.stop()

    app = FastAPI(title="Device Bus Analyzer", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(PKG.joinpath("static"))), name="static")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # --- helpers ---------------------------------------------------------------
    def ctx(request: Request, **kw: Any) -> dict[str, Any]:
        lang = i18n.pick(request.headers.get("accept-language"), request.cookies.get("dba_lang"), request.query_params.get("lang"))
        return {"request": request, "t": i18n.STR[lang], "logout_csrf": auth.csrf_for(request.cookies.get(COOKIE, "")),
                "logged_in": auth.valid_session(request.cookies.get(COOKIE)), "lang": lang, "tz": str(tz), "version": __version__,
                "has_src": "src" in kw, "fmt": lambda ts: datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if ts else "-",
                "hexs": lambda b: bytes(b).hex() if b is not None else "", **kw}

    def page(request: Request, name: str, **kw: Any) -> HTMLResponse:
        c = ctx(request, **kw)
        resp = tpl.TemplateResponse(request, name, c)
        if request.query_params.get("lang") in i18n.STR:
            resp.set_cookie("dba_lang", c["lang"], max_age=365 * 86400, samesite="lax")
        return resp

    def authed(request: Request) -> bool:
        return auth.valid_session(request.cookies.get(COOKIE)) or auth.valid_token(request.headers.get("authorization"))

    def need_user(request: Request) -> None:
        if not authed(request):
            if request.url.path.startswith("/api/"):
                raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": "Bearer"})
            raise HTTPException(303, headers={"Location": "/login"})

    def source_or_404(name: str) -> dict:
        s = store.source_by_name(name)
        if not s:
            raise HTTPException(404, "unknown source")
        return s

    def window(source: str, run: int | None, since: float | None, until: float | None) -> tuple[float | None, float | None]:
        """A run id narrows the query to that run (including the context before its start)."""
        if run is None:
            return since, until
        r = store.run(source, run)
        if r is None:
            raise HTTPException(404, "unknown run")
        return r["from_ts"], r["end_ts"] + 60

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "?"

    # --- login ----------------------------------------------------------------
    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        token = secrets.token_urlsafe(24)
        resp = page(request, "login.html", error=None, csrf=token)
        resp.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="strict", secure=settings.cookie_secure, max_age=900)
        return resp

    @app.post("/login", response_class=HTMLResponse)
    def login(request: Request, email: str = Form(...), password: str = Form(...), csrf: str = Form(...)):
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not cookie or not secrets.compare_digest(cookie, csrf):
            raise HTTPException(403, "bad CSRF token")
        ip = client_ip(request)
        if auth.locked(ip):
            r = page(request, "login.html", error="locked", csrf=csrf)
            r.status_code = 429
            return r
        if not auth.check_login(ip, email, password):
            r = page(request, "login.html", error="bad", csrf=csrf)
            r.status_code = 401
            return r
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, auth.make_session(), httponly=True, samesite="strict", secure=settings.cookie_secure,
                        max_age=auth.max_age)
        resp.delete_cookie(CSRF_COOKIE)
        return resp

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form(...)):
        if not auth.valid_session(request.cookies.get(COOKIE)) or not secrets.compare_digest(
                auth.csrf_for(request.cookies.get(COOKIE, "")), csrf):
            raise HTTPException(403, "bad CSRF token")
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE)
        return resp

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__}

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        if exc.status_code == 303:
            return RedirectResponse(exc.headers["Location"], status_code=303)
        if request.url.path.startswith("/api/") or exc.status_code in (401, 403, 422):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
        return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)

    # --- JSON API (read-only; used by the frontend, scripts and the MCP server) ------
    api = Depends(need_user)

    @app.get("/api/sources", dependencies=[api])
    def api_sources():
        return store.sources()

    @app.get("/api/{source}/frames", dependencies=[api])
    def api_frames(source: str, ds: str | None = None, cmd: str | None = None, since: str | None = None,
                   until: str | None = None, bad_only: bool = False, limit: int = 200, offset: int = 0, run: int | None = None):
        source_or_404(source)
        lo, hi = window(source, run, parse_time(since, tz), parse_time(until, tz))
        rows = store.frames(source, parse_hex(ds, 2), parse_hex(cmd, 4), lo, hi,
                            False if bad_only else None, max(1, min(limit, 5000)), max(0, offset))
        return jsonable(rows)

    @app.get("/api/{source}/timeline", dependencies=[api])
    def api_timeline(source: str, since: str | None = None, until: str | None = None, limit: int = 2000, run: int | None = None):
        source_or_404(source)
        lo, hi = window(source, run, parse_time(since, tz), parse_time(until, tz))
        return jsonable(store.timeline(source, lo, hi, max(1, min(limit, 20000))))

    @app.get("/api/{source}/runs", dependencies=[api])
    def api_runs(source: str):
        source_or_404(source)
        return store.runs(source)

    @app.get("/api/{source}/commands", dependencies=[api])
    def api_commands(source: str):
        source_or_404(source)
        return store.command_stats(source)

    @app.get("/api/{source}/commands/{ds}/{cmd}/values", dependencies=[api])
    def api_values(source: str, ds: str, cmd: str, limit: int = 50):
        source_or_404(source)
        return jsonable(store.command_values(source, parse_hex(ds, 2) or 0, parse_hex(cmd, 4) or 0, max(1, min(limit, 500))))

    @app.get("/api/{source}/bursts", dependencies=[api])
    def api_bursts(source: str, since: str | None = None, until: str | None = None, limit: int = 200, offset: int = 0,
                   run: int | None = None):
        source_or_404(source)
        lo, hi = window(source, run, parse_time(since, tz), parse_time(until, tz))
        return jsonable(store.bursts(source, lo, hi, max(1, min(limit, 5000)), max(0, offset)))

    @app.get("/api/{source}/quality", dependencies=[api])
    def api_quality(source: str):
        source_or_404(source)
        return store.quality(source)

    @app.get("/api/spec/{protocol}", dependencies=[api])
    def api_spec(protocol: str):
        try:
            spec = load_spec(protocol)
        except (FileNotFoundError, OSError):
            raise HTTPException(404, "unknown protocol") from None
        return {k: v for k, v in spec.items() if not k.startswith("_")}

    # --- device management (HTML forms only: session + CSRF; the bearer token can never change configuration) ---
    def ago(ts: float | None, lang: str) -> str:
        if not ts:
            return i18n.STR[lang]["never"]
        sec = max(0, int(time.time() - ts))
        t = i18n.STR[lang]
        for limit, div, unit in ((60, 1, "s"), (3600, 60, "min"), (86400, 3600, "h"), (10 ** 9, 86400, "d")):
            if sec < limit:
                return t["ago"].format(f"{sec // div} {t[unit]}")
        return ""

    def device_state(d: dict) -> str:
        if not d["host"]:
            return "import"
        if not d["enabled"]:
            return "paused"
        return "live" if d["last_seen"] and time.time() - d["last_seen"] < 150 else "waiting"

    def devices_page(request: Request, error: str | None = None, form: dict | None = None, status: int = 200):
        lang = i18n.pick(request.headers.get("accept-language"), request.cookies.get("dba_lang"), request.query_params.get("lang"))
        rows = store.devices()
        for d in rows:
            d["state"], d["ago"] = device_state(d), ago(d["last_seen"], lang)
        resp = page(request, "devices.html", devices=rows, catalog=catalog.build(store.used_classifications()),
                    error=error, form=form)
        resp.status_code = status
        return resp

    def need_session(request: Request) -> None:
        """Configuration pages (hosts, deletion) need a real login session; the API token only reads data."""
        if not auth.valid_session(request.cookies.get(COOKIE)):
            raise HTTPException(303, headers={"Location": "/login"})

    cfg = Depends(need_session)

    def need_session_csrf(request: Request, csrf: str) -> None:
        cookie = request.cookies.get(COOKIE)
        if not auth.valid_session(cookie):
            raise HTTPException(303, headers={"Location": "/login"})
        if not secrets.compare_digest(auth.csrf_for(cookie or ""), csrf):
            raise HTTPException(403, "bad CSRF token")

    @app.get("/devices", response_class=HTMLResponse, dependencies=[cfg])
    def devices_list(request: Request):
        return devices_page(request)

    async def save_device(request: Request, name: str, creating: bool, csrf: str, form: dict) -> Response:
        need_session_csrf(request, csrf)
        existing = store.device(name)
        try:
            if creating:
                if existing and existing["configured"]:
                    raise ValueError("exists")
                protocol = form["protocol"]
            else:
                if not existing:
                    raise HTTPException(404, "unknown device")
                protocol = existing["protocol"]            # fixed once data exists: the decoder must not change underneath it
            if not form["host"]:
                raise ValueError("bad_host")
            port, key = validate_device_input(name, form["host"], form["port"], protocol, form["key"], protocols.PROTOCOLS)
            store.save_device(name, protocol, form["type"] or None, form["manufacturer"] or None, form["model"] or None,
                              form["host"], port, key, clear_key=form["clear_key"], enabled=form["enabled"])
        except ValueError as exc:
            msg = str(exc)
            code = msg if msg in i18n.STR["en"] else "bad_input"
            return devices_page(request, code, {**form, "name": name, "key": "", "creating": creating}, 422)
        if start_collectors:
            manager.sync()
        target = f"/firmware/{protocol}?device={name}&new=1" if creating else "/devices"
        return RedirectResponse(target, status_code=303)

    def device_form(type, manufacturer, model, protocol, host, port, key, clear_key, enabled) -> dict:
        return {"type": type.strip(), "manufacturer": manufacturer.strip(), "model": model.strip(), "protocol": protocol,
                "host": host.strip(), "port": port.strip(), "key": key, "clear_key": clear_key == "1", "enabled": enabled == "1"}

    @app.post("/devices")
    async def device_create(request: Request, csrf: str = Form(...), name: str = Form(...), type: str = Form(""),
                            manufacturer: str = Form(""), model: str = Form(""), protocol: str = Form(""), host: str = Form(""),
                            port: str = Form("6053"), key: str = Form(""), enabled: str = Form("")):
        return await save_device(request, name.strip(), True, csrf,
                                 device_form(type, manufacturer, model, protocol, host, port, key, "", enabled))

    @app.post("/devices/{name}")
    async def device_update(request: Request, name: str, csrf: str = Form(...), type: str = Form(""), manufacturer: str = Form(""),
                            model: str = Form(""), host: str = Form(""), port: str = Form("6053"), key: str = Form(""),
                            clear_key: str = Form(""), enabled: str = Form("")):
        return await save_device(request, name, False, csrf,
                                 device_form(type, manufacturer, model, "", host, port, key, clear_key, enabled))

    @app.post("/devices/{name}/enabled")
    async def device_toggle(request: Request, name: str, csrf: str = Form(...), enabled: str = Form("")):
        need_session_csrf(request, csrf)
        if not store.set_enabled(name, enabled == "1"):
            raise HTTPException(404, "unknown device")
        if start_collectors:
            manager.sync()
        return RedirectResponse("/devices", status_code=303)

    @app.get("/devices/{name}/delete", response_class=HTMLResponse, dependencies=[cfg])
    def device_delete_confirm(request: Request, name: str):
        counts = store.data_counts(name)
        if counts is None:
            raise HTTPException(404, "unknown device")
        return page(request, "device_delete.html", device=store.device(name), counts=counts, error=None)

    @app.post("/devices/{name}/delete")
    async def device_delete(request: Request, name: str, csrf: str = Form(...), confirm: str = Form("")):
        need_session_csrf(request, csrf)
        counts = store.data_counts(name)
        if counts is None:
            raise HTTPException(404, "unknown device")
        if confirm.strip() != name:                       # the name must be typed: no accidental deletes
            r = page(request, "device_delete.html", device=store.device(name), counts=counts, error="confirm_mismatch")
            r.status_code = 422
            return r
        manager.stop_device(name)                         # first stop the collector: nothing may be stored after the delete
        store.delete_device(name)
        if start_collectors:
            manager.sync()
        return RedirectResponse("/devices", status_code=303)

    # --- firmware: the recommended ESPHome files of a protocol, to read, copy and download ---------------------------
    @app.get("/firmware/{protocol}", response_class=HTMLResponse, dependencies=[api])
    def firmware_page(request: Request, protocol: str, device: str = "", new: str = ""):
        lang = i18n.pick(request.headers.get("accept-language"), request.cookies.get("dba_lang"), request.query_params.get("lang"))
        prof = catalog.firmware_profile(protocol, lang)
        if prof is None:
            raise HTTPException(404, "no firmware for this protocol")
        dev = store.device(device) if device else None
        return page(request, "firmware.html", protocol=protocol, prof=prof, device=dev if dev and dev["protocol"] == protocol else None,
                    new=bool(new))

    @app.get("/firmware/{protocol}/{filename}", dependencies=[api])
    def firmware_download(protocol: str, filename: str):
        prof = catalog.firmware_profile(protocol)
        text = next((f["text"] for f in prof["files"] if f["name"] == filename), None) if prof else None
        if text is None:                                  # only files named by the catalogue for this protocol are ever served
            raise HTTPException(404, "unknown file")
        return Response(text, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    # --- HTML ---------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse, dependencies=[api])
    def index(request: Request):
        # The start page is the device list (there is no separate "sources" tab). Holders of the API token only read the data pages.
        if auth.valid_session(request.cookies.get(COOKIE)):
            return devices_page(request)
        return page(request, "index.html", sources=store.sources())

    @app.get("/s/{source}/frames", response_class=HTMLResponse, dependencies=[api])
    def html_frames(request: Request, source: str, ds: str = "", cmd: str = "", since: str = "", until: str = "",
                    bad_only: bool = False, limit: int = 200, offset: int = 0, run: str = ""):
        src = source_or_404(source)
        limit = max(1, min(limit, 1000))
        run_id = int(run) if run.isdigit() else None
        lo, hi = window(source, run_id, parse_time(since, tz), parse_time(until, tz))
        rows = store.frames(source, parse_hex(ds, 2), parse_hex(cmd, 4), lo, hi, False if bad_only else None, limit, max(0, offset))
        return page(request, "frames.html", src=src, rows=rows, q=dict(ds=ds, cmd=cmd, since=since, until=until, bad_only=bad_only,
                    limit=limit, offset=max(0, offset), run=run))

    @app.get("/s/{source}/timeline", response_class=HTMLResponse, dependencies=[api])
    def html_timeline(request: Request, source: str, since: str = "", until: str = "", limit: int = 1000, run: str = ""):
        src = source_or_404(source)
        lo, hi = window(source, int(run) if run.isdigit() else None, parse_time(since, tz), parse_time(until, tz))
        rows = store.timeline(source, lo, hi, max(1, min(limit, 5000)))
        for r in rows:
            r["marker"] = None
        if rows:     # what the person did at the appliance is shown between the telegrams, at the time it happened
            for m in store.markers(source, since=rows[0]["ts"], until=rows[-1]["ts"] + 1):
                rows.append({"ts": m["ts"], "marker": m})
            rows.sort(key=lambda r: (r["ts"], r["marker"] is None))
        return page(request, "timeline.html", src=src, rows=rows, q=dict(since=since, until=until, limit=limit, run=run))

    @app.get("/s/{source}/runs", response_class=HTMLResponse, dependencies=[api])
    def html_runs(request: Request, source: str):
        src = source_or_404(source)
        return page(request, "runs.html", src=src, runs=list(reversed(store.runs(source))))

    @app.get("/s/{source}/commands", response_class=HTMLResponse, dependencies=[api])
    def html_commands(request: Request, source: str, ds: str = "", cmd: str = ""):
        src = source_or_404(source)
        stats = store.command_stats(source)
        values = store.command_values(source, parse_hex(ds, 2) or 0, parse_hex(cmd, 4) or 0) if ds and cmd else []
        return page(request, "commands.html", src=src, stats=stats, values=values, sel=(ds, cmd))

    @app.get("/s/{source}/bursts", response_class=HTMLResponse, dependencies=[api])
    def html_bursts(request: Request, source: str, since: str = "", until: str = "", limit: int = 100, offset: int = 0, run: str = ""):
        src = source_or_404(source)
        lo, hi = window(source, int(run) if run.isdigit() else None, parse_time(since, tz), parse_time(until, tz))
        rows = store.bursts(source, lo, hi, max(1, min(limit, 1000)), max(0, offset))
        return page(request, "bursts.html", src=src, rows=rows, q=dict(since=since, until=until, limit=limit, offset=max(0, offset), run=run))

    @app.get("/s/{source}/quality", response_class=HTMLResponse, dependencies=[api])
    def html_quality(request: Request, source: str):
        src = source_or_404(source)
        return page(request, "quality.html", src=src, q=store.quality(source))

    @app.get("/findings/{protocol}", response_class=HTMLResponse, dependencies=[api])
    def html_findings(request: Request, protocol: str):
        try:
            spec = load_spec(protocol)
        except (FileNotFoundError, OSError):
            raise HTTPException(404, "unknown protocol") from None
        return page(request, "findings.html", spec=spec, protocol=protocol)

    # --- companion: mark what is done at the appliance, learn from it ------------------------------------
    def rules_for(source: str) -> dict:
        d = store.device(source)
        return catalog.event_rules(d["type"] if d else None)

    def lang_of(request: Request) -> str:
        return i18n.pick(request.headers.get("accept-language"), request.cookies.get("dba_lang"), request.query_params.get("lang"))

    @app.get("/s/{source}/companion", response_class=HTMLResponse, dependencies=[cfg])
    def html_companion(request: Request, source: str):
        src = source_or_404(source)
        d = store.device(source)
        return page(request, "companion.html", src=src, device=d, controls=catalog.controls(d["type"] if d else None, lang_of(request)),
                    markers=store.markers(source, limit=15, newest_first=True))

    @app.post("/s/{source}/markers")
    async def marker_create(request: Request, source: str, csrf: str = Form(...), kind: str = Form(...), label: str = Form(""),
                            menu: str = Form(""), note: str = Form(""), step_group: str = Form("")):
        need_session_csrf(request, csrf)
        source_or_404(source)
        d = store.device(source)
        events = {e["id"]: e for e in catalog.controls(d["type"] if d else None, lang_of(request))["events"]}
        if kind in events:
            label = events[kind]["label"]                                     # the server owns the wording of presets
        elif kind == "custom":
            if not label.strip():
                raise HTTPException(422, "label required")
        else:
            raise HTTPException(422, "unknown kind")
        # Instant action; a guided step with a duration is closed later through /end (the time span is what is analysed).
        return JSONResponse(store.add_marker(source, kind, label, menu or None, note or None, step_group=step_group or None))

    @app.post("/s/{source}/markers/{marker_id}/end")
    async def marker_end(request: Request, source: str, marker_id: int, csrf: str = Form(...), note: str = Form("")):
        need_session_csrf(request, csrf)
        m = store.marker(source, marker_id)
        if not m:
            raise HTTPException(404, "unknown marker")
        label = m["label"].split(":")[0] + (": " + note.strip() if note.strip() else "")
        return JSONResponse(store.end_marker(source, marker_id, note=note, label=label if note.strip() else None))

    @app.post("/s/{source}/markers/{marker_id}/delete")
    async def marker_delete(request: Request, source: str, marker_id: int, csrf: str = Form(...)):
        need_session_csrf(request, csrf)
        if not store.delete_marker(source, marker_id):
            raise HTTPException(404, "unknown marker")
        return JSONResponse({"ok": True})

    activity_cache: dict[tuple, dict] = {}

    @app.get("/s/{source}/activity", dependencies=[cfg])
    def marker_activity(source: str, since: float):
        source_or_404(source)
        now = time.time()
        key = (source, int(since), int(now / 2))
        if key not in activity_cache:
            if len(activity_cache) > 50:
                activity_cache.clear()
            activity_cache[key] = analysis.activity(store, source, since, now, rules_for(source))
        return JSONResponse(activity_cache[key])

    def learn_context(request: Request, source: str) -> dict:
        src = source_or_404(source)
        res = analysis.run(store, source, rules_for(source))
        return {"src": src, "res": res, "learned": store.learned(source), "device": store.device(source),
                "min_baseline": analysis.MIN_BASELINE, "marker_rows": store.markers(source, limit=1)}

    @app.get("/s/{source}/learn", response_class=HTMLResponse, dependencies=[api])
    def html_learn(request: Request, source: str, error: str = ""):
        return page(request, "learn.html", error=error, **learn_context(request, source))

    @app.post("/s/{source}/learned")
    async def learned_create(request: Request, source: str, csrf: str = Form(...), group: str = Form(...), ds: int = Form(...),
                             cmd: int = Form(...), pos: int = Form(...), meaning: str = Form("")):
        need_session_csrf(request, csrf)
        source_or_404(source)
        res = analysis.run(store, source, rules_for(source))              # recomputed: only what the analysis really found is stored
        g = next((x for x in res["groups"] if x["key"] == group), None)
        c = next((x for x in (g["candidates"] if g else []) if (x["ds"], x["cmd"], x["pos"]) == (ds, cmd, pos)), None)
        if not c or c["status"] not in ("assumed", "confirmed"):
            raise HTTPException(422, "no such finding")
        store.save_learned(source, meaning.strip() or g["label"], g["kind"], ds, cmd, pos, c["from"], c["to"], c["hits"], c["n"], c["status"])
        return RedirectResponse(f"/s/{source}/learn#learned", status_code=303)

    @app.post("/s/{source}/learned/{learned_id}/delete")
    async def learned_delete(request: Request, source: str, learned_id: int, csrf: str = Form(...)):
        need_session_csrf(request, csrf)
        if not store.delete_learned(source, learned_id):
            raise HTTPException(404, "unknown finding")
        return RedirectResponse(f"/s/{source}/learn#learned", status_code=303)

    @app.get("/s/{source}/contribution.json", dependencies=[api])
    def contribution(source: str):
        """What may leave this installation: accepted findings and a count of actions. No frames, no timestamps, no host, no key."""
        src = source_or_404(source)
        d = store.device(source) or {}
        kinds = Counter(m["kind"] for m in store.markers(source, limit=5000))
        out = {"format": 1, "protocol": src["protocol"], "type": d.get("type"), "manufacturer": d.get("manufacturer"), "model": d.get("model"),
               "findings": [{"meaning": f["meaning"], "action": f["kind"], "ds": f["ds"], "cmd": f["cmd"], "byte": f["pos"], "from": f["from_val"],
                             "to": f["to_val"], "repeats": f["hits"], "of": f["n"], "status": f["status"]} for f in store.learned(source)],
               "actions_recorded": dict(kinds)}
        return Response(json.dumps(out, indent=2, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{source}-findings.json"'})

    @app.get("/api/{source}/markers", dependencies=[api])
    def api_markers(source: str, limit: int = 500):
        source_or_404(source)
        return store.markers(source, limit=limit)

    @app.get("/api/{source}/learn", dependencies=[api])
    def api_learn(source: str):
        source_or_404(source)
        return analysis.run(store, source, rules_for(source))

    return app
