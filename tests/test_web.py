import re

import pytest
from conftest import raw1
from fastapi.testclient import TestClient

from device_bus_analyzer.config import Settings
from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.web import create_app

MAIL, PW, TOKEN = "admin@example.org", "correct horse battery", "tok-123456"


@pytest.fixture
def app(store):
    sid = store.source("dw", "bshdbus")
    for i, minutes in enumerate((160, 160, 159), start=1):
        store.ingest_line(sid, raw1(i, i * 1_000_000, build_frame(0x25, 0x2008, bytes([minutes]) + bytes(7)) + b"\x2a"), 1_800_000_000.0 + i)
    store.ingest_line(sid, raw1(4, 4_000_000, build_frame(0x17, 0x1010, b"\x1c")), 1_800_000_004.0)
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token=TOKEN)
    return create_app(s, store)


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


def login(c, email=MAIL, pw=PW):
    page = c.get("/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    return c.post("/login", data={"email": email, "password": pw, "csrf": csrf})


def test_requires_login(client):
    assert client.get("/").status_code == 303 and client.get("/").headers["location"] == "/login"
    assert client.get("/api/sources").status_code == 401
    assert client.get("/s/dw/frames").status_code == 303


def test_login_success_sets_hardened_cookie(client):
    r = login(client)
    assert r.status_code == 303
    c = r.headers["set-cookie"].lower()
    assert "httponly" in c and "samesite=strict" in c
    assert client.get("/").status_code == 200


def test_wrong_password_and_wrong_email_rejected(client):
    assert login(client, pw="nope").status_code == 401
    assert login(client, email="x@example.org").status_code == 401
    assert client.get("/").status_code == 303


def test_login_requires_csrf(client):
    client.get("/login")
    r = client.post("/login", data={"email": MAIL, "password": PW, "csrf": "forged"})
    assert r.status_code == 403
    assert client.post("/login", data={"email": MAIL, "password": PW}).status_code == 422


def test_login_rate_limit(client):
    for _ in range(5):
        assert login(client, pw="bad").status_code == 401
    assert login(client).status_code == 429             # correct password is refused while locked


def test_email_is_case_insensitive(client):
    assert login(client, email=MAIL.upper()).status_code == 303


def test_logout_needs_csrf_and_clears_session(client):
    login(client)
    html = client.get("/").text
    token = re.search(r'action="/logout".*?value="([^"]+)"', html, re.S).group(1)
    assert client.post("/logout", data={"csrf": "x"}).status_code == 403
    assert client.post("/logout", data={"csrf": token}).status_code == 303
    assert client.get("/").status_code == 303          # server-side response of logout cleared the cookie


def test_tampered_session_cookie_is_rejected(client):
    client.cookies.set("dba_session", "forged.value.here")
    assert client.get("/").status_code == 303


def test_api_with_bearer_token(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get("/api/sources", headers=h).json()[0]["name"] == "dw"
    assert client.get("/api/sources", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/sources", headers={"Authorization": TOKEN}).status_code == 401


def test_api_frames_filters_and_decoding(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    rows = client.get("/api/dw/frames", params={"cmd": "2008"}, headers=h).json()
    assert [r["decoded"]["values"]["remaining_min"] for r in rows] == [160, 160, 159]
    assert rows[0]["data"].startswith("a0") and rows[0]["ack"] == 0x2A
    assert len(client.get("/api/dw/frames", params={"ds": "17"}, headers=h).json()) == 1
    assert len(client.get("/api/dw/frames", params={"limit": 2}, headers=h).json()) == 2
    assert client.get("/api/dw/frames", params={"bad_only": "true"}, headers=h).json() == []


def test_api_time_filter_accepts_epoch_and_iso(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    assert len(client.get("/api/dw/frames", params={"since": "1800000003"}, headers=h).json()) == 2
    assert client.get("/api/dw/frames", params={"since": "2099-01-01T00:00"}, headers=h).json() == []
    assert client.get("/api/dw/frames", params={"since": "garbage"}, headers=h).status_code == 422


def test_api_timeline_commands_bursts_quality_spec(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    tl = client.get("/api/dw/timeline", headers=h).json()
    assert [t["decoded"]["values"].get("remaining_min") for t in tl if t["cmd"] == 0x2008] == [160, 159]
    cs = client.get("/api/dw/commands", headers=h).json()
    assert {(c["ds"], c["cmd"]) for c in cs} == {(0x25, 0x2008), (0x17, 0x1010)}
    assert client.get("/api/dw/commands/25/2008/values", headers=h).json()[0]["n"] == 2
    assert len(client.get("/api/dw/bursts", headers=h).json()) == 4
    assert client.get("/api/dw/quality", headers=h).json()["ok"] == 4
    assert client.get("/api/spec/bshdbus", headers=h).json()["protocol"] == "bshdbus"
    assert client.get("/api/spec/nope", headers=h).status_code == 404


def test_validation_and_unknown_source(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get("/api/nobody/frames", headers=h).status_code == 404
    assert client.get("/api/dw/frames", params={"cmd": "zz"}, headers=h).status_code == 422
    assert client.get("/api/dw/frames", params={"cmd": "12345"}, headers=h).status_code == 422


@pytest.mark.parametrize("lang,word", [("de", "Telegramme"), ("en", "Frames")])
def test_html_pages_render_in_both_languages(client, lang, word):
    login(client)
    for path in ("/", "/s/dw/frames", "/s/dw/timeline", "/s/dw/commands", "/s/dw/commands?ds=25&cmd=2008",
                 "/s/dw/bursts", "/s/dw/quality", "/findings/bshdbus", "/findings/macs"):
        r = client.get(path, params={"lang": lang} if "?" not in path else None, headers={"Accept-Language": lang})
        assert r.status_code == 200, path
    assert word in client.get("/s/dw/frames", params={"lang": lang}).text


def test_html_shows_decoded_values_and_status_badges(client):
    login(client)
    t = client.get("/s/dw/frames?cmd=2008&lang=en").text
    assert "Remaining time" in t and "confirmed" in t and "<b>160 min</b>" in t


def test_security_headers_and_no_store(client):
    r = client.get("/login")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"


def test_no_write_routes_exist(app):
    for r in app.routes:
        methods = getattr(r, "methods", None) or set()
        if r.path.startswith("/api") or r.path.startswith("/s/"):
            assert methods <= {"GET", "HEAD"}, r.path
    # configuration (devices) is changed only through session + CSRF forms; no route can delete or send anything to a device
    assert {r.path for r in app.routes if "POST" in (getattr(r, "methods", None) or set())} == {"/login", "/logout", "/devices", "/devices/{name}"}
    assert not [r.path for r in app.routes if {"DELETE", "PUT", "PATCH"} & (getattr(r, "methods", None) or set())]


def test_startup_needs_admin_settings(store):
    with pytest.raises(RuntimeError):
        create_app(Settings(), store)


def test_password_hash_variant(store):
    from argon2 import PasswordHasher
    s = Settings(admin_email=MAIL, admin_password_hash=PasswordHasher().hash("hash-pw"), session_secret="s" * 32)
    c = TestClient(create_app(s, store), follow_redirects=False)
    assert login(c, pw="hash-pw").status_code == 303


def test_healthz_is_public_and_minimal(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_broken_device_entry_does_not_stop_the_app(store):
    from device_bus_analyzer.config import Device
    store.source("dw", "bshdbus")
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32,
                 devices=[Device("dw", "192.0.2.9", 6053, "macs")])      # conflicts with the stored protocol
    with TestClient(create_app(s, store, start_collectors=True)) as c:
        assert c.get("/healthz").json()["status"] == "ok"


def test_protocol_conflict_message_names_both_values(store):
    store.source("dw", "bshdbus")
    with pytest.raises(ValueError, match="stored with protocol 'bshdbus' but was requested with 'macs'"):
        store.source("dw", "macs")


def test_invalid_hash_falls_back_to_plain_password(store):
    s = Settings(admin_email=MAIL, admin_password=PW, admin_password_hash="argon2id v19 m65536 mangled", session_secret="s" * 32)
    c = TestClient(create_app(s, store), follow_redirects=False)
    assert login(c).status_code == 303


def test_invalid_hash_without_password_fails_clearly(store):
    with pytest.raises(RuntimeError, match="not a valid argon2 hash"):
        create_app(Settings(admin_email=MAIL, admin_password_hash="garbage", session_secret="s" * 32), store)


def test_failed_login_is_logged_without_secrets(client, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="dba.auth"):
        login(client, email="other@example.org", pw="very-secret-wrong")
        login(client, pw="very-secret-wrong")
    text = caplog.text
    assert "does not match" in text and "wrong" in text and "very-secret-wrong" not in text and PW not in text


def test_html_marks_assumed_sender_ack_and_fields(client):
    login(client)
    t = client.get("/s/dw/frames?cmd=2008&lang=en").text
    assert "Sender" in t and "power module" in t and "assumed" in t         # sender + ACK node carry a badge
    t = client.get("/s/dw/frames?lang=de").text
    assert "Absender" in t and "angenommen" in t
    assert "unbekannt" in client.get("/s/dw/commands?lang=de").text or "bestätigt" in client.get("/s/dw/commands?lang=de").text
    assert "Knoten" in client.get("/findings/bshdbus?lang=de").text


def test_api_exposes_sender_and_status(client):
    h = {"Authorization": f"Bearer {TOKEN}"}
    d = client.get("/api/dw/frames", params={"cmd": "2008", "limit": 1}, headers=h).json()[0]["decoded"]
    assert d["sender"]["value"] == "power module" and d["sender"]["status"] == "assumed"
    assert d["acked_by"]["status"] == "assumed" and d["fields"][0]["status"] == "confirmed"


def _run_data(store):
    sid = store.source("dw2", "bshdbus")
    n = [0]

    def put(ts, fr):
        n[0] += 1
        store.ingest_line(sid, raw1(n[0], n[0] * 1000, fr), ts)
    put(1000.0, build_frame(0x17, 0x1011, b"\x1c"))
    put(1010.0, build_frame(0x17, 0x1013, b"\x01"))
    put(1010.2, build_frame(0x17, 0x1013, b"\x01"))                 # repeated start burst is merged
    for k in range(4):
        put(1060.0 + 60 * k, build_frame(0x25, 0x2008, bytes([160 - k]) + bytes(7)))
    put(9000.0, build_frame(0x17, 0x1011, b"\x0d"))
    put(9010.0, build_frame(0x17, 0x1013, b"\x01"))
    put(9070.0, build_frame(0x25, 0x2008, bytes([150]) + bytes(7)))
    return store


def test_runs_are_detected_and_marked_assumed(store):
    runs = _run_data(store).runs("dw2")
    assert len(runs) == 2
    r = runs[0]
    assert (r["program"], r["remaining_start_min"], r["remaining_end_min"]) == ("Chef 70 C", 160, 157)
    assert r["start_status"] == "assumed" and r["end_status"] == "assumed" and r["open"] is False
    assert r["frames"] == 6 and runs[1]["program"] == "Auto 45-65 C"
    assert runs[1]["from_ts"] > r["end_ts"]                          # context never reaches into the previous run


def test_macs_source_without_frames_has_no_runs(store):
    store.source("tr", "macs")
    assert store.runs("tr") == []


def test_api_and_html_run_filter(store):
    from argon2 import PasswordHasher  # noqa: F401
    _run_data(store)
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token=TOKEN), store),
                   follow_redirects=False)
    h = {"Authorization": f"Bearer {TOKEN}"}
    runs = c.get("/api/dw2/runs", headers=h).json()
    first, second = runs[0]["id"], runs[1]["id"]
    in_first = c.get("/api/dw2/frames", params={"run": first, "limit": 100}, headers=h).json()
    assert len(in_first) == 7 and all(f["ts"] < 5000 for f in in_first)       # selection + start + 4 status frames (+ merged repeat)
    assert all(f["ts"] > 5000 for f in c.get("/api/dw2/frames", params={"run": second}, headers=h).json())
    assert len(c.get("/api/dw2/timeline", params={"run": first}, headers=h).json()) > 0
    assert c.get("/api/dw2/bursts", params={"run": first}, headers=h).json()
    assert c.get("/api/dw2/frames", params={"run": 999999}, headers=h).status_code == 404
    login(c)
    t = c.get(f"/s/dw2/runs?lang=de").text
    assert "Läufe" in t and "angenommen" in t and "Chef 70 C" in t and f"run={first}" in t
    assert "Lauf #" in c.get(f"/s/dw2/frames?run={first}&lang=de").text
    assert c.get("/s/dw2/runs?lang=en").status_code == 200


def test_macs_pages_show_devices_and_decoded_frames(store):
    from device_bus_analyzer.protocols import macs
    sid = store.source("tr", "macs")
    hb = macs.build_frame(0x2A, 0x22, bytes.fromhex("5f03"))
    store.ingest_line(sid, raw1(1, 1_000_000, hb + macs.build_ack(hb)), 1_800_000_001.0)
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token=TOKEN), store),
                   follow_redirects=False)
    login(c)
    en, de = c.get("/findings/macs?lang=en").text, c.get("/findings/macs?lang=de").text
    assert "Devices" in en and "0x22" in en and "M1IB1606" in en and "Geräte" in de and "Adresse" in de
    page = c.get("/s/tr/frames?lang=en").text
    assert "dryer control board" in page and "2a" in page and "225f" in page
    h = {"Authorization": f"Bearer {TOKEN}"}
    f = c.get("/api/tr/frames", headers=h).json()
    assert f[0]["decoded"]["name"] == "heartbeat" and f[0]["decoded"]["sender"]["status"] == "assumed"
