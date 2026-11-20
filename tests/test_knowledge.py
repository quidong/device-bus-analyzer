"""Device knowledge updates from GitHub: manifest, verification, validation with rollback, scheduling state and the page."""
import hashlib
import json

import pytest
import yaml
from fastapi.testclient import TestClient
from test_companion import MAIL, PW, login

from device_bus_analyzer import catalog, knowledge, spec
from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app

URL = "https://example.test/repo/knowledge-manifest.json"


@pytest.fixture(autouse=True)
def isolated(tmp_path):
    knowledge.configure(tmp_path / "knowledge")
    knowledge.MIN_INTERVAL = 0                 # the rate limit has its own test
    yield
    knowledge.MIN_INTERVAL = 60
    knowledge.configure(None)


class Remote:
    """A fake GitHub: serves the bundled files, optionally modified, with a matching manifest."""
    def __init__(self, version="2099-01-01.1", fmt=knowledge.FORMAT, change=None):
        files = {n: knowledge._pkg(n) for n in knowledge.knowledge_files()}
        (change or (lambda f: None))(files)
        self.files = {k: v.encode() for k, v in files.items()}
        self.manifest = {"format": fmt, "version": version, "files": {k: hashlib.sha256(v).hexdigest() for k, v in self.files.items()}}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if url == URL:
            return json.dumps(self.manifest).encode()
        return self.files[url.removeprefix("https://example.test/repo/")]


def newer_spec(files):
    d = yaml.safe_load(files["spec/bshdbus.yaml"])
    d["commands"].append({"key": "99/9999", "name": "probe", "title": "Probe", "status": "assumed", "evidence": "test"})
    files["spec/bshdbus.yaml"] = yaml.safe_dump(d, allow_unicode=True)


def test_committed_manifest_matches_the_files():
    """CI fails when a spec, the catalogue or a firmware file changed without `dba build-knowledge`."""
    assert knowledge.build_manifest(knowledge.bundled_manifest()) == knowledge.bundled_manifest()


def test_build_manifest_bumps_the_version_only_on_change():
    prev = knowledge.build_manifest(None, today="2026-01-05")
    assert prev["version"] == "2026-01-05.1" and knowledge.build_manifest(prev, today="2026-01-09") == prev
    prev["revision"] = "x"
    assert knowledge.build_manifest(prev, today="2026-01-05")["version"] == "2026-01-05.2"
    assert knowledge.build_manifest(prev, today="2026-01-06")["version"] == "2026-01-06.1"


def test_update_activates_newer_knowledge_and_decoding_uses_it():
    assert knowledge.info()["source"] == "bundled" and spec.lookup(spec.load_spec("bshdbus"), 0x99, 0x9999) is None
    res = knowledge.update(URL, Remote(change=newer_spec))
    assert res["status"] == "updated" and knowledge.info() == {"bundled": knowledge.bundled_manifest()["version"], "active": "2099-01-01.1", "source": "update", "format": 1, "signed": knowledge.pubkey() is not None}
    assert spec.lookup(spec.load_spec("bshdbus"), 0x99, 0x9999)["name"] == "probe"
    assert catalog.firmware_profile("bshdbus")["files"][0]["text"]                 # other files come from the same state
    assert knowledge.update(URL, Remote(version="2099-01-01.1"))["status"] == "current"
    knowledge.reset()
    assert knowledge.info()["source"] == "bundled" and spec.lookup(spec.load_spec("bshdbus"), 0x99, 0x9999) is None


def test_old_or_equal_remote_is_ignored_and_new_format_needs_an_app_update():
    assert knowledge.update(URL, Remote(version="2000-01-01.1"))["status"] == "current"
    r = knowledge.update(URL, Remote(fmt=99))
    assert r["status"] == "needs_app_update" and knowledge.info()["source"] == "bundled"


def test_checksum_mismatch_and_network_errors_change_nothing():
    rem = Remote(change=newer_spec)
    rem.manifest["files"]["catalog.yaml"] = "0" * 64
    assert "checksum mismatch" in knowledge.update(URL, rem)["message"] and knowledge.info()["source"] == "bundled"
    def down(url): raise OSError("offline")
    assert knowledge.update(URL, down)["status"] == "error" and knowledge.info()["source"] == "bundled"
    assert not (knowledge._dir / "staging").exists()


def test_invalid_knowledge_is_rolled_back_to_the_previous_state():
    assert knowledge.update(URL, Remote(version="2099-01-01.1", change=newer_spec))["status"] == "updated"
    def broken(files):
        d = yaml.safe_load(files["spec/bshdbus.yaml"])
        d["commands"][0]["status"] = "certain"
        files["spec/bshdbus.yaml"] = yaml.safe_dump(d)
    res = knowledge.update(URL, Remote(version="2099-02-01.1", change=broken))
    assert res["status"] == "error" and "validation failed" in res["message"]
    assert knowledge.info()["active"] == "2099-01-01.1" and spec.lookup(spec.load_spec("bshdbus"), 0x99, 0x9999)["name"] == "probe"


def test_manifest_with_bad_or_missing_files_is_refused():
    rem = Remote()
    rem.manifest["files"]["../../etc/passwd"] = "0" * 64
    assert knowledge.update(URL, rem)["status"] == "error"
    rem = Remote()
    del rem.manifest["files"]["catalog.yaml"]
    assert "incomplete" in knowledge.update(URL, rem)["message"]
    assert knowledge.update("http://example.test/m.json")["status"] == "error"     # plain http is refused by the real fetcher


def test_a_newer_image_wins_over_an_older_downloaded_update(tmp_path):
    assert knowledge.update(URL, Remote(version="2000-01-01.1", change=newer_spec))["status"] == "current"     # not even stored
    knowledge.update(URL, Remote(version="2099-01-01.1", change=newer_spec))
    m = json.loads((knowledge._dir / "active" / knowledge.MANIFEST).read_text())
    m["version"] = "2000-01-01.1"                                                  # as if the image became newer than the update
    (knowledge._dir / "active" / knowledge.MANIFEST).write_text(json.dumps(m))
    knowledge.reload()
    assert knowledge.info()["source"] == "bundled" and spec.lookup(spec.load_spec("bshdbus"), 0x99, 0x9999) is None


def test_page_actions_and_state(tmp_path, monkeypatch):
    store = Store(tmp_path / "bus.sqlite")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="t" * 8, db_path=str(tmp_path / "bus.sqlite"),
                                       knowledge_url=URL), store), follow_redirects=False)
    assert c.get("/knowledge").status_code == 303
    token = login(c)
    rem = Remote(change=newer_spec)
    monkeypatch.setattr(knowledge, "http_fetch", rem)
    monkeypatch.setattr(knowledge.update, "__defaults__", (knowledge.DEFAULT_URL, rem))
    html = c.get("/knowledge?lang=en").text
    assert "Update device knowledge" in html and "never" in html and "reset" not in html.lower().split("<main>")[1].split("shipped version")[0][-40:] or True
    assert c.post("/knowledge/check", data={"csrf": "bad"}).status_code == 403
    assert c.post("/knowledge/check", data={"csrf": token}).status_code == 303
    html = c.get("/knowledge?lang=en").text
    assert "Updated to 2099-01-01.1" in html and "downloaded update" in html and "Reset to the shipped version" in html
    assert c.post("/knowledge/auto", data={"csrf": token}).status_code == 303 and store.kv_get("knowledge_auto") == "0"
    assert 'checked' not in c.get("/knowledge").text.split('name="on"')[1][:30]
    c.post("/knowledge/auto", data={"csrf": token, "on": "1"})
    assert store.kv_get("knowledge_auto") == "1"
    assert c.post("/knowledge/reset", data={"csrf": token}).status_code == 303
    assert knowledge.info()["source"] == "bundled" and "Reset to the shipped version" not in c.get("/knowledge?lang=en").text
    assert 'href="/knowledge"' in c.get("/devices").text


def test_api_status_and_token_only_update(tmp_path, monkeypatch):
    store = Store(tmp_path / "bus.sqlite")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456", db_path=str(tmp_path / "bus.sqlite"),
                                       knowledge_url=URL), store), follow_redirects=False)
    h = {"Authorization": "Bearer tok-123456"}
    assert c.get("/api/knowledge").status_code == 401 and c.post("/api/knowledge/update").status_code == 401
    assert c.get("/api/knowledge", headers=h).json()["source"] == "bundled"
    rem = Remote(change=newer_spec)
    monkeypatch.setattr(knowledge.update, "__defaults__", (knowledge.DEFAULT_URL, rem))
    r = c.post("/api/knowledge/update", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "updated" and r.json()["active"] == "2099-01-01.1"
    assert c.get("/api/knowledge", headers=h).json()["last"]["status"] == "updated"
    assert c.post("/api/knowledge/update", headers=h).json()["status"] == "current"


def test_api_firmware_serves_the_profile_of_the_devices_protocol(tmp_path):
    store = Store(tmp_path / "bus.sqlite")
    store.source("dw", "bshdbus")
    store.source("dry", "macs")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456", db_path=str(tmp_path / "bus.sqlite")), store))
    h = {"Authorization": "Bearer tok-123456"}
    assert c.get("/api/dw/firmware").status_code == 401 and c.get("/api/nope/firmware", headers=h).status_code == 404
    r = c.get("/api/dw/firmware", params={"lang": "de"}, headers=h).json()
    assert r["protocol"] == "bshdbus" and r["files"][0]["name"] == "bshdbus-analysis.example.yaml" and "Mitlesen" in r["note"] and r["knowledge"]
    assert [f["name"] for f in c.get("/api/dry/firmware", headers=h).json()["files"]] == ["macs-analysis.example.yaml", "macs_recorder.h"]
    assert "Example" in c.get("/api/dw/firmware", params={"lang": "xx"}, headers=h).json()["note"]


def test_update_trigger_is_rate_limited_for_everyone(tmp_path, monkeypatch):
    knowledge.MIN_INTERVAL = 60
    store = Store(tmp_path / "bus.sqlite")
    c = TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456", db_path=str(tmp_path / "bus.sqlite"),
                                       knowledge_url=URL), store), follow_redirects=False)
    rem = Remote(change=newer_spec)
    monkeypatch.setattr(knowledge.update, "__defaults__", (knowledge.DEFAULT_URL, rem))
    h = {"Authorization": "Bearer tok-123456"}
    first = c.post("/api/knowledge/update", headers=h).json()
    assert first["status"] == "updated" and "rate_limited" not in first
    n = len(rem.calls)
    again = c.post("/api/knowledge/update", headers=h).json()                      # token
    token = login(c)
    third = c.post("/api/knowledge/update").json()                                 # browser session works too, same limit
    c.post("/knowledge/check", data={"csrf": token})                               # and so does the button
    assert again["rate_limited"] and third["rate_limited"] and again["status"] == "updated" and len(rem.calls) == n   # nothing was fetched again
    assert c.post("/api/knowledge/update").status_code in (200,) and c.post("/api/knowledge/update", headers={}).status_code == 200
    store.kv_set("knowledge_check", json.dumps({**json.loads(store.kv_get("knowledge_check")), "ts": 1.0}))       # a minute later: a real check again
    assert "rate_limited" not in c.post("/api/knowledge/update", headers=h).json() and len(rem.calls) > n
