"""Backup download/restore, help page and the start checklist."""
import sqlite3

from fastapi.testclient import TestClient
from test_companion import MAIL, PW, login

from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


def make(tmp_path, name="a.sqlite"):
    store = Store(tmp_path / name)
    store.source("dw", "bshdbus")
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413", "secret.lan", 6053, None)
    app = create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456"), store)
    return store, TestClient(app, follow_redirects=False)


def test_backup_needs_a_session_and_download_is_a_valid_snapshot(tmp_path):
    store, c = make(tmp_path)
    assert c.get("/backup").status_code == 303 and c.get("/backup/download").status_code == 303
    assert c.get("/backup/download", headers={"Authorization": "Bearer tok-123456"}).status_code == 303   # token does not suffice
    login(c)
    r = c.get("/backup/download")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    f = tmp_path / "dl.sqlite"
    f.write_bytes(r.content)
    assert Store.check_backup(f) is None and sqlite3.connect(f).execute("SELECT name FROM sources").fetchall() == [("dw",)]


def test_restore_replaces_the_data_and_rejects_bad_input(tmp_path):
    store, c = make(tmp_path)
    token = login(c)
    snap = c.get("/backup/download").content
    store.delete_device("dw")
    assert store.devices() == []
    post = lambda data, confirm="RESTORE", t=token: c.post("/backup/restore", data={"csrf": t, "confirm": confirm}, files={"file": ("b.sqlite", data)})
    assert post(snap, t="bad").status_code == 403
    assert post(snap, confirm="no").status_code == 422
    assert post(b"not a database").status_code == 422
    other = tmp_path / "other.sqlite"
    sqlite3.connect(other).execute("CREATE TABLE x(a)").connection.commit()
    assert post(other.read_bytes()).status_code == 422
    assert store.devices() == []                                    # failed attempts changed nothing
    r = post(snap)
    assert r.status_code == 303 and r.headers["location"] == "/backup?msg=restored"
    assert [d["name"] for d in store.devices()] == ["dw"]
    assert "Backup restored" in c.get("/backup?msg=restored&lang=en").text


def test_help_page_and_header_links(tmp_path):
    store, c = make(tmp_path)
    assert c.get("/help").status_code in (303, 401)
    login(c)
    h = c.get("/help?lang=en").text
    assert "How to record a good run" in h and "step" not in h.split("<h1>")[0]
    assert 'href="/help"' in c.get("/devices").text and 'href="/backup"' in c.get("/devices").text


def test_start_checklist_tracks_progress(tmp_path):
    store, c = make(tmp_path)
    login(c)
    html = c.get("/devices?lang=en").text
    assert "Getting started" in html and html.count('class="done"') == 1       # only the device exists
    store.add_marker("dw", "instant", "x", ts=1.0)
    assert html != c.get("/devices?lang=en").text
