"""HTTPS in the LAN: local CA + server certificate, renewal, a real TLS server, CA download and the health check."""
import datetime as dt
import ssl
import threading
import time
import urllib.request

import pytest
import uvicorn
from cryptography import x509
from test_companion import MAIL, PW, login
from fastapi.testclient import TestClient

from device_bus_analyzer import cli, config, tls
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


def test_ensure_creates_a_ca_and_a_server_certificate_with_the_requested_names(tmp_path):
    f = tls.ensure(tmp_path, ["analyzer.lan", "192.0.2.10"])
    assert f.ca and not f.own and {"localhost", "127.0.0.1", "analyzer.lan", "192.0.2.10"} <= set(f.hosts)
    ca = x509.load_pem_x509_certificate(open(f.ca, "rb").read())
    leaf = x509.load_pem_x509_certificate(open(f.cert, "rb").read())
    assert leaf.issuer == ca.subject and ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert not leaf.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert (tmp_path / "tls" / "server.key").stat().st_mode & 0o777 == 0o600 and (tmp_path / "tls" / "ca.key").stat().st_mode & 0o777 == 0o600
    assert (leaf.not_valid_after_utc - dt.datetime.now(dt.timezone.utc)).days > 700


def test_ensure_is_stable_and_reissues_only_the_leaf_when_names_change(tmp_path):
    a = tls.ensure(tmp_path, ["a.lan"])
    ca_bytes, leaf_bytes = open(a.ca, "rb").read(), open(a.cert, "rb").read()
    again = tls.ensure(tmp_path, ["a.lan"])
    assert open(again.cert, "rb").read() == leaf_bytes
    b = tls.ensure(tmp_path, ["a.lan", "b.lan"])
    assert open(b.ca, "rb").read() == ca_bytes and open(b.cert, "rb").read() != leaf_bytes and "b.lan" in b.hosts      # CA unchanged: no new trust step


def test_expiring_leaf_is_renewed(tmp_path, monkeypatch):
    tls.ensure(tmp_path, [])
    before = open(tmp_path / "tls" / "server.crt", "rb").read()
    monkeypatch.setattr(tls, "RENEW_BEFORE_DAYS", 10_000)
    assert open(tls.ensure(tmp_path, []).cert, "rb").read() != before


def test_own_certificate_is_used_as_it_is(tmp_path):
    f = tls.ensure(tmp_path / "x", ["h.lan"])
    own = tls.ensure(tmp_path / "y", [], own_cert=f.cert, own_key=f.key)
    assert own.own and own.ca is None and own.cert == f.cert


def test_settings_default_to_plain_http_and_https_is_opt_in():
    d = config.load({"ADMIN_EMAIL": "a@b.de"})
    assert not d.tls and not d.cookie_secure
    s = config.load({"DBA_TLS": "1", "DBA_TLS_HOSTS": "a.lan, 10.0.0.2"})
    assert s.tls and s.cookie_secure and s.tls_hosts == ["a.lan", "10.0.0.2"]
    assert config.load({"COOKIE_SECURE": "1"}).cookie_secure and not config.load({"DBA_TLS": "1", "COOKIE_SECURE": "0"}).cookie_secure


@pytest.fixture
def tls_server(tmp_path):
    files = tls.ensure(tmp_path, [])
    store = Store(tmp_path / "bus.sqlite")
    app = create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456789012345", db_path=str(tmp_path / "bus.sqlite")), store)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, ssl_certfile=files.cert, ssl_keyfile=files.key, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    port = srv.servers[0].sockets[0].getsockname()[1]
    yield files, port
    srv.should_exit = True
    t.join(5)


def test_a_real_https_request_verifies_against_the_local_ca_only(tls_server):
    f, port = tls_server
    url = f"https://127.0.0.1:{port}/healthz"
    ctx = ssl.create_default_context(cafile=f.ca)
    assert urllib.request.urlopen(url, context=ctx, timeout=5).status == 200
    with pytest.raises(Exception, match="CERTIFICATE_VERIFY_FAILED|certificate"):
        urllib.request.urlopen(url, context=ssl.create_default_context(), timeout=5)                       # unknown CA is rejected, as it must be
    ca = urllib.request.urlopen(f"https://127.0.0.1:{port}/tls/ca.crt", context=ctx, timeout=5).read()
    assert ca == open(f.ca, "rb").read() and b"PRIVATE" not in ca                                          # public part only


def test_healthcheck_command_accepts_https_with_a_private_ca(tls_server, monkeypatch):
    f, port = tls_server
    monkeypatch.setenv("DBA_PORT_INTERNAL", str(port))
    monkeypatch.setenv("ADMIN_EMAIL", MAIL)
    assert cli.main(["healthcheck"]) == 0
    monkeypatch.setenv("DBA_PORT_INTERNAL", "1")
    assert cli.main(["healthcheck"]) == 1


def test_tls_page_and_ca_download_in_the_app(tmp_path):
    tls.ensure(tmp_path, ["analyzer.lan"])
    store = Store(tmp_path / "bus.sqlite")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="t" * 20, db_path=str(tmp_path / "bus.sqlite")), store),
                   follow_redirects=False)
    assert c.get("/tls").status_code == 303                                          # the page needs a login ...
    r = c.get("/tls/ca.crt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-x509-ca-cert")    # ... the public CA certificate does not
    login(c)
    html = c.get("/tls?lang=en").text
    assert "analyzer.lan" in html and "Install the CA certificate" in html and "SHA-256" in html and 'href="/tls/ca.crt"' in html
    assert 'href="/tls"' in c.get("/devices").text
    other = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, db_path=str(tmp_path / "none" / "bus.sqlite")), Store(tmp_path / "o.sqlite")))
    assert other.get("/tls/ca.crt").status_code == 404


def test_node_extension_trusts_only_the_analyzers_own_ca(tls_server):
    import os
    import subprocess
    from pathlib import Path
    f, port = tls_server
    ext = Path(__file__).resolve().parent.parent / "extension"
    if not (ext / "node_modules").is_dir():
        pytest.skip("npm ci --prefix extension not run")
    r = subprocess.run(["node", "test/tls.mjs"], cwd=ext, capture_output=True, text=True, timeout=60,
                       env={**os.environ, "DBA_URL": f"https://127.0.0.1:{port}", "DBA_TOKEN": "tok-123456789012345", "DBA_CA": f.ca})
    assert r.returncode == 0 and "tls OK" in r.stdout, r.stdout + r.stderr


# --- secrets created on the first start ---------------------------------------------------------------------
def test_secrets_are_created_once_and_kept(tmp_path):
    s = Settings(admin_email=MAIL, db_path=str(tmp_path / "bus.sqlite"))
    config.ensure_secrets(s)
    assert len(s.session_secret) >= 32 and len(s.api_token) >= 16
    f = tmp_path / "secrets.json"
    assert f.stat().st_mode & 0o777 == 0o600
    again = config.ensure_secrets(Settings(admin_email=MAIL, db_path=str(tmp_path / "bus.sqlite")))
    assert (again.session_secret, again.api_token) == (s.session_secret, s.api_token)         # a restart keeps sessions and the token valid


def test_secrets_from_the_stack_are_adopted_and_win(tmp_path):
    import json
    db = str(tmp_path / "bus.sqlite")
    s = config.ensure_secrets(Settings(admin_email=MAIL, db_path=db, session_secret="e" * 40, api_token="old-token-from-yaml-123"))
    assert (s.session_secret, s.api_token) == ("e" * 40, "old-token-from-yaml-123")
    assert json.loads((tmp_path / "secrets.json").read_text()) == {"session_secret": "e" * 40, "api_token": "old-token-from-yaml-123"}
    gone = config.ensure_secrets(Settings(admin_email=MAIL, db_path=db))                       # the lines were removed from the YAML later
    assert (gone.session_secret, gone.api_token) == ("e" * 40, "old-token-from-yaml-123")      # same values: nothing breaks
    changed = config.ensure_secrets(Settings(admin_email=MAIL, db_path=db, api_token="new-token-from-yaml-4567"))
    assert changed.api_token == "new-token-from-yaml-4567" and changed.session_secret == "e" * 40
    assert config.ensure_secrets(Settings(admin_email=MAIL, db_path=db)).api_token == "new-token-from-yaml-4567"


def test_unwritable_data_directory_keeps_the_old_behaviour(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    s = config.ensure_secrets(Settings(admin_email=MAIL, db_path=str(blocker / "sub" / "bus.sqlite")))
    assert s.session_secret == "" and s.api_token == ""


def test_mcp_page_shows_the_generated_token(tmp_path):
    from fastapi.testclient import TestClient
    store = Store(tmp_path / "m.sqlite")
    s = config.ensure_secrets(Settings(admin_email=MAIL, admin_password=PW, db_path=str(tmp_path / "m.sqlite")))
    c = TestClient(create_app(s, store), follow_redirects=False)
    login(c)
    assert s.api_token in c.get("/mcp").text


# --- header menu and live regions ---------------------------------------------------------------------------
def test_header_has_account_menu_with_language_select_and_pages_are_live(tmp_path):
    from fastapi.testclient import TestClient
    store = Store(tmp_path / "h.sqlite")
    store.source("dw", "bshdbus")
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", None)
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-1234567890abcdef"), store), follow_redirects=False)
    login(c)
    html = c.get("/devices").text
    assert 'class="usermenu"' in html and "data-lang-select" in html and "?lang=" not in html.split("</header>")[0]
    for href in ("/help", "/mcp", "/knowledge", "/tls", "/backup"):
        assert f'href="{href}"' in html.split("</header>")[0]
    assert 'data-live="state-dw"' in html and 'data-live="values-dw"' in html and "data-live-keys=" in html
    assert 'data-live="runs"' in c.get("/s/dw/runs").text
    assert c.get("/static/ui.js").status_code == 200


# --- settings page ----------------------------------------------------------------------------------------
def _settings_client(tmp_path, name="s"):
    from fastapi.testclient import TestClient
    store = Store(tmp_path / f"{name}.sqlite")
    s = config.ensure_secrets(Settings(admin_email=MAIL, admin_password=PW, db_path=str(tmp_path / f"{name}.sqlite")))
    c = TestClient(create_app(s, store), follow_redirects=False)
    login(c)
    return c, s, store


def _csrf(c):
    import re
    return re.search(r'name="csrf" value="([0-9a-f]+)"', c.get("/settings").text).group(1)


def test_settings_save_applies_and_persists(tmp_path):
    c, s, store = _settings_client(tmp_path)
    r = c.post("/settings", data={"csrf": _csrf(c), "tz": "America/New_York", "session_hours": "48", "knowledge_url": "https://example.org/m.json", "tls_hosts": "a.lan"})
    assert r.headers["location"] == "/settings?msg=restart"                                          # the certificate names changed
    assert (s.tz, s.session_hours, s.knowledge_url) == ("America/New_York", 48, "https://example.org/m.json")
    assert 'value="America/New_York"' in c.get("/settings").text
    s2 = config.apply_saved(Settings(admin_email=MAIL, admin_password=PW, tz="Europe/Berlin"), store.kv_get("config"))      # a restart reads the same values
    assert (s2.tz, s2.session_hours, s2.tls_hosts) == ("America/New_York", 48, ["a.lan"])
    r = c.post("/settings", data={"csrf": _csrf(c), "tz": "Europe/Berlin", "session_hours": "48", "tls_hosts": "a.lan"})
    assert r.headers["location"] == "/settings?msg=saved"                                            # nothing that needs a restart
    r = c.post("/settings", data={"csrf": _csrf(c), "tz": "Europe/Berlin", "session_hours": "48", "tls": "1", "tls_hosts": "a.lan"})
    assert r.headers["location"] == "/settings?msg=restart"                                          # HTTPS needs a restart


def test_settings_validation_and_csrf(tmp_path):
    c, s, store = _settings_client(tmp_path)
    good = {"csrf": _csrf(c), "tz": "Europe/Berlin", "session_hours": "12"}
    for bad, code in (({"tz": "Mars/Base"}, "tz"), ({"session_hours": "0"}, "hours"), ({"session_hours": "x"}, "hours"),
                      ({"knowledge_url": "ftp://x"}, "url"), ({"tls_hosts": "bad host!"}, "hosts")):
        assert c.post("/settings", data={**good, **bad}).headers["location"] == f"/settings?error={code}"
    assert c.post("/settings", data={**good, "csrf": "wrong"}).status_code == 403
    assert store.kv_get("config") is None and s.tz == "Europe/Berlin"


def test_token_renewal_and_password_change(tmp_path):
    c, s, store = _settings_client(tmp_path)
    old = s.api_token
    assert c.post("/settings/token", data={"csrf": _csrf(c)}).headers["location"] == "/settings?msg=token"
    assert s.api_token != old and s.api_token in c.get("/mcp").text
    from fastapi.testclient import TestClient
    anon = TestClient(c.app, follow_redirects=False)                                                 # no session cookie: only the token counts
    assert anon.get("/api/sources", headers={"authorization": "Bearer " + s.api_token}).status_code == 200
    assert anon.get("/api/sources", headers={"authorization": "Bearer " + old}).status_code == 401
    assert config.ensure_secrets(Settings(admin_email=MAIL, db_path=s.db_path)).api_token == s.api_token      # kept across restarts
    t = _csrf(c)
    assert c.post("/settings/password", data={"csrf": t, "current": "nope", "new": "a-long-new-pass", "again": "a-long-new-pass"}).headers["location"] == "/settings?error=pw_current"
    assert c.post("/settings/password", data={"csrf": t, "current": PW, "new": "short", "again": "short"}).headers["location"] == "/settings?error=pw_new"
    assert c.post("/settings/password", data={"csrf": t, "current": PW, "new": "a-long-new-pass", "again": "a-long-new-pass"}).headers["location"] == "/settings?msg=password"
    from fastapi.testclient import TestClient
    c2 = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, db_path=s.db_path, session_secret="z" * 40), store), follow_redirects=False)
    import re
    tok = re.search(r'name="csrf" value="([^"]+)"', c2.get("/login").text).group(1)
    assert c2.post("/login", data={"email": MAIL, "password": PW, "csrf": tok}).status_code != 303      # the old password no longer works
    tok = re.search(r'name="csrf" value="([^"]+)"', c2.get("/login").text).group(1)
    assert c2.post("/login", data={"email": MAIL, "password": "a-long-new-pass", "csrf": tok}).status_code == 303


def test_menu_links_to_settings(tmp_path):
    c, s, store = _settings_client(tmp_path)
    assert 'href="/settings"' in c.get("/devices").text


def test_menu_is_grouped_and_every_subpage_leads_back_to_the_devices(tmp_path):
    c, s, store = _settings_client(tmp_path)
    store.source("dw", "bshdbus")
    menu = c.get("/devices").text.split("</header>")[0]
    for group in ("menu_account", "menu_connect", "menu_system"):
        assert f'<div class="gh">{__import__("device_bus_analyzer.i18n", fromlist=["STR"]).STR["en"][group]}</div>' in menu
    assert 'class="crumb' not in menu                                                       # the start page itself needs no way back
    for path in ("/settings", "/help", "/mcp", "/knowledge", "/tls", "/backup", "/s/dw/frames", "/s/dw/companion"):
        head = c.get(path, params={"lang": "en"}).text.split("</header>")[0]
        assert 'class="crumb' in head and 'href="/"' in head, path
