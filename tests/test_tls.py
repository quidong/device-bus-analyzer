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


def test_settings_defaults_to_https_and_secure_cookies(monkeypatch):
    assert config.load({"ADMIN_EMAIL": "a@b.de"}).tls and config.load({"ADMIN_EMAIL": "a@b.de"}).cookie_secure
    s = config.load({"DBA_TLS": "0", "DBA_TLS_HOSTS": "a.lan, 10.0.0.2"})
    assert not s.tls and not s.cookie_secure and s.tls_hosts == ["a.lan", "10.0.0.2"]
    assert config.load({"DBA_TLS": "0", "COOKIE_SECURE": "1"}).cookie_secure


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
