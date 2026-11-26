"""Findings of the security review: secret strength, token guessing, real sign-out, headers, free text, restore and update inputs."""
import hashlib
import json
import sqlite3
import urllib.request

import pytest
from fastapi.testclient import TestClient
from test_companion import MAIL, PW, login
from test_knowledge import URL, Remote

from device_bus_analyzer import knowledge
from device_bus_analyzer.auth import Auth
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


def make(tmp_path, **kw):
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456789012345", db_path=str(tmp_path / "a.sqlite"), **kw)
    store = Store(tmp_path / "a.sqlite")
    return store, TestClient(create_app(s, store), follow_redirects=False)


def test_short_session_secret_is_refused_and_weak_ones_warned(caplog):
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Auth(Settings(admin_email=MAIL, admin_password=PW, session_secret="short"))
    Auth(Settings(admin_email=MAIL, admin_password=PW, session_secret="x" * 20, api_token="abc"))
    assert "fewer than 32" in caplog.text and "fewer than 16" in caplog.text


def test_api_token_guessing_is_throttled(tmp_path):
    store, c = make(tmp_path)
    for _ in range(5):
        assert c.get("/api/sources", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/sources", headers={"Authorization": "Bearer wrong"}).status_code == 429
    assert c.get("/api/sources", headers={"Authorization": "Bearer tok-123456789012345"}).status_code == 429     # locked for this address
    assert login(c)                                                                                               # the password login is a separate counter


def test_correct_token_and_sessions_never_count_as_failures(tmp_path):
    store, c = make(tmp_path)
    for _ in range(20):
        assert c.get("/api/sources", headers={"Authorization": "Bearer tok-123456789012345"}).status_code == 200
    login(c)
    for _ in range(20):
        assert c.get("/api/sources", headers={"Authorization": "Bearer garbage"}).status_code == 200     # a valid session is enough


def test_logout_really_ends_the_session(tmp_path):
    store, c = make(tmp_path)
    token = login(c)
    cookie = c.cookies.get("dba_session")
    assert c.get("/devices").status_code == 200
    assert c.post("/logout", data={"csrf": token}).status_code == 303
    c.cookies.set("dba_session", cookie)                       # an attacker replays the copied cookie
    assert c.get("/devices").status_code == 303 and c.get("/api/sources").status_code == 401


def test_security_headers(tmp_path):
    store, c = make(tmp_path)
    h = c.get("/login").headers
    assert h["x-frame-options"] == "DENY" and "camera=()" in h["permissions-policy"]
    assert h["cross-origin-opener-policy"] == "same-origin" and h["cross-origin-resource-policy"] == "same-origin"
    assert h["content-security-policy"].startswith("default-src 'self'") and h["cache-control"] == "no-store"


def test_device_free_text_is_bounded_and_without_control_characters(tmp_path):
    store, c = make(tmp_path)
    token = login(c)
    r = c.post("/devices", data={"csrf": token, "name": "x1", "type": "dishwasher", "manufacturer": "Ne\x00ff\n" + "A" * 200, "model": "M\x07" * 100,
                                 "protocol": "bshdbus", "host": "h.lan", "port": "6053", "enabled": "1"})
    assert r.status_code == 303
    d = store.device("x1")
    assert len(d["manufacturer"]) <= 60 and len(d["model"]) <= 60 and all(ch.isprintable() for ch in d["manufacturer"] + d["model"])


def test_restore_refuses_files_with_triggers_views_or_virtual_tables(tmp_path):
    store, c = make(tmp_path)
    token = login(c)
    snap = c.get("/backup/download").content
    for evil in ("CREATE TRIGGER t AFTER INSERT ON frames BEGIN DELETE FROM sources; END",
                 "CREATE VIEW v AS SELECT * FROM sources"):
        f = tmp_path / "evil.sqlite"
        f.write_bytes(snap)
        con = sqlite3.connect(f)
        con.execute(evil)
        con.commit()
        con.close()
        r = c.post("/backup/restore", data={"csrf": token, "confirm": "RESTORE"}, files={"file": ("e.sqlite", f.read_bytes())})
        assert r.status_code == 422 and "triggers or views" in c.post("/backup/restore?lang=en", data={"csrf": token, "confirm": "RESTORE"},
                                                                      files={"file": ("e.sqlite", f.read_bytes())}).text
    assert store.devices() == []
    assert c.post("/backup/restore", data={"csrf": token, "confirm": "RESTORE"}, files={"file": ("ok.sqlite", snap)}).status_code == 303


# --- knowledge updates -----------------------------------------------------------------------------------------------------
@pytest.fixture
def kn(tmp_path, monkeypatch):
    knowledge.configure(tmp_path / "knowledge")
    monkeypatch.setattr(knowledge, "pubkey", lambda: None)      # these checks run behind the signature; it has its own tests
    knowledge.MIN_INTERVAL = 0
    yield
    knowledge.MIN_INTERVAL = 60
    knowledge.configure(None)


def test_download_refuses_redirects_to_plain_http():
    h = knowledge._HttpsOnly()
    req = urllib.request.Request("https://example.test/a")
    with pytest.raises(ValueError, match="non-https"):
        h.redirect_request(req, None, 302, "Found", {}, "http://evil.test/a")


def test_alias_bomb_and_file_flood_are_refused(kn):
    def bomb(files):
        files["catalog.yaml"] += "\n" + "\n".join(f"x{i}: *dishwasher" for i in range(60))
    r = knowledge.update(URL, Remote(change=bomb))
    assert r["status"] == "error" and "aliases" in r["message"] and knowledge.info()["source"] == "bundled"
    rem = Remote()
    for i in range(70):
        rem.manifest["files"][f"firmware/f{i}.h"] = hashlib.sha256(b"x").hexdigest()
    assert knowledge.update(URL, rem)["message"] == "too many files"


def test_the_real_catalogue_stays_under_the_alias_limit():
    import re
    assert len(re.findall(rb"(?m)(?:^|[\s:\[,{-])\*[A-Za-z0-9_-]+", knowledge._pkg("catalog.yaml").encode())) < knowledge.MAX_ALIASES
