"""FastAPI application: read-only JSON API (/api) and HTML frontend. Nothing here can write to a device."""
from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from importlib import resources
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__, i18n
from .auth import COOKIE, CSRF_COOKIE, Auth
from .config import Settings
from .spec import load_spec
from .store import Store

PKG = resources.files("device_bus_analyzer")


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
    collectors: list[asyncio.Task] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_collectors and settings.devices:
            from .collector import Collector
            collectors.extend(asyncio.create_task(Collector(store, d).run_forever()) for d in settings.devices)
        yield
        for t in collectors:
            t.cancel()

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
                "fmt": lambda ts: datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if ts else "-",
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
                   until: str | None = None, bad_only: bool = False, limit: int = 200, offset: int = 0):
        source_or_404(source)
        rows = store.frames(source, parse_hex(ds, 2), parse_hex(cmd, 4), parse_time(since, tz), parse_time(until, tz),
                            False if bad_only else None, max(1, min(limit, 5000)), max(0, offset))
        return jsonable(rows)

    @app.get("/api/{source}/timeline", dependencies=[api])
    def api_timeline(source: str, since: str | None = None, until: str | None = None, limit: int = 2000):
        source_or_404(source)
        return jsonable(store.timeline(source, parse_time(since, tz), parse_time(until, tz), max(1, min(limit, 20000))))

    @app.get("/api/{source}/commands", dependencies=[api])
    def api_commands(source: str):
        source_or_404(source)
        return store.command_stats(source)

    @app.get("/api/{source}/commands/{ds}/{cmd}/values", dependencies=[api])
    def api_values(source: str, ds: str, cmd: str, limit: int = 50):
        source_or_404(source)
        return jsonable(store.command_values(source, parse_hex(ds, 2) or 0, parse_hex(cmd, 4) or 0, max(1, min(limit, 500))))

    @app.get("/api/{source}/bursts", dependencies=[api])
    def api_bursts(source: str, since: str | None = None, until: str | None = None, limit: int = 200, offset: int = 0):
        source_or_404(source)
        return jsonable(store.bursts(source, parse_time(since, tz), parse_time(until, tz), max(1, min(limit, 5000)), max(0, offset)))

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

    # --- HTML ---------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse, dependencies=[api])
    def index(request: Request):
        return page(request, "index.html", sources=store.sources())

    @app.get("/s/{source}/frames", response_class=HTMLResponse, dependencies=[api])
    def html_frames(request: Request, source: str, ds: str = "", cmd: str = "", since: str = "", until: str = "",
                    bad_only: bool = False, limit: int = 200, offset: int = 0):
        src = source_or_404(source)
        limit = max(1, min(limit, 1000))
        rows = store.frames(source, parse_hex(ds, 2), parse_hex(cmd, 4), parse_time(since, tz), parse_time(until, tz),
                            False if bad_only else None, limit, max(0, offset))
        return page(request, "frames.html", src=src, rows=rows, q=dict(ds=ds, cmd=cmd, since=since, until=until, bad_only=bad_only,
                    limit=limit, offset=max(0, offset)))

    @app.get("/s/{source}/timeline", response_class=HTMLResponse, dependencies=[api])
    def html_timeline(request: Request, source: str, since: str = "", until: str = "", limit: int = 1000):
        src = source_or_404(source)
        rows = store.timeline(source, parse_time(since, tz), parse_time(until, tz), max(1, min(limit, 5000)))
        return page(request, "timeline.html", src=src, rows=rows, q=dict(since=since, until=until, limit=limit))

    @app.get("/s/{source}/commands", response_class=HTMLResponse, dependencies=[api])
    def html_commands(request: Request, source: str, ds: str = "", cmd: str = ""):
        src = source_or_404(source)
        stats = store.command_stats(source)
        values = store.command_values(source, parse_hex(ds, 2) or 0, parse_hex(cmd, 4) or 0) if ds and cmd else []
        return page(request, "commands.html", src=src, stats=stats, values=values, sel=(ds, cmd))

    @app.get("/s/{source}/bursts", response_class=HTMLResponse, dependencies=[api])
    def html_bursts(request: Request, source: str, since: str = "", until: str = "", limit: int = 100, offset: int = 0):
        src = source_or_404(source)
        rows = store.bursts(source, parse_time(since, tz), parse_time(until, tz), max(1, min(limit, 1000)), max(0, offset))
        return page(request, "bursts.html", src=src, rows=rows, q=dict(since=since, until=until, limit=limit, offset=max(0, offset)))

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

    return app
