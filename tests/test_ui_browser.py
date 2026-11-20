"""Real-browser check of the companion and the responsive layout (skipped when Playwright or Chrome is not installed)."""
import shutil
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
pytestmark = pytest.mark.skipif(not CHROME, reason="no Chrome/Chromium available")

import uvicorn  # noqa: E402

from device_bus_analyzer.config import Settings  # noqa: E402
from device_bus_analyzer.store import Store  # noqa: E402
from device_bus_analyzer.web import create_app  # noqa: E402

MAIL, PW = "admin@example.org", "correct horse battery"


@pytest.fixture
def server(tmp_path):
    store = Store(tmp_path / "ui.sqlite")
    store.source("dw", "bshdbus")
    store.save_device("dw", "bshdbus", "dishwasher", "Neff", "S413K60S0E", None)
    s = Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token="tok-123456")
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = uvicorn.Server(uvicorn.Config(create_app(s, store), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", store
    srv.should_exit = True; th.join(5); store.close()


@pytest.mark.parametrize("width", [1100, 390])
def test_guided_run_and_pages_without_overflow(server, width):
    base, store = server
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": width, "height": 800}); errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base + "/login?lang=en"); pg.fill("input[name=email]", MAIL); pg.fill("input[name=password]", PW); pg.click("button")
        for path in ("/", "/devices", "/s/dw/companion", "/s/dw/learn", "/s/dw/timeline", "/firmware/bshdbus", "/help", "/backup", "/mcp", "/s/dw/homeassistant"):
            for lang in ("en", "fr"):               # fr: the longest strings
                pg.goto(base + path + "?lang=" + lang)
                assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0, (path, width, lang)
        pg.goto(base + "/s/dw/companion?lang=en&fast=1")                   # fast=1: every timer runs at a quarter of the time
        pg.fill("#cp-menu", "Main menu")
        pg.click("button.ev:has-text('Start pressed')")
        pg.wait_for_selector("#cp-list li:has-text('Start pressed')")
        pg.click("button.ev:has-text('Program selected')")
        assert pg.is_visible("#cp-ask"); pg.fill("#cp-ask-note", "Eco 50"); pg.click("#cp-ask-ok")
        pg.wait_for_selector("#cp-list li:has-text('Eco 50')")
        kinds = [m["kind"] for m in store.markers("dw")]
        assert kinds == ["start", "program"] and store.markers("dw")[0]["menu"] == "Main menu"
        # guided door check: 3 rounds x (open, close)
        pg.click("#cp-scripts button:has-text('Open and close the door')")
        assert pg.is_visible("#cp-go") and not pg.is_visible("#cp-done") and not pg.is_visible("#cp-text")      # first screen: only "Go", no instruction
        assert not pg.is_visible("#cp-lead")
        pg.click("#cp-go")
        pg.wait_for_selector("#cp-text:has-text('Hands off')")        # 90 s hands-off phase first (measures the noise), then the steps
        for i in range(6):                                          # "Go" once; every step then shows its instruction and "Done"
            pg.wait_for_selector("#cp-done:visible")
            assert pg.is_visible("#cp-text") and not pg.is_visible("#cp-go")
            assert ("Open the door" if i % 2 == 0 else "Close the door") in pg.inner_text("#cp-text")
            pg.click("#cp-done")
            if i < 5:
                pg.wait_for_selector("#cp-progress:has-text('Step %d of')" % (i + 2))
        pg.wait_for_selector("#cp-end:visible")
        done = store.markers("dw")[3:]
        assert store.markers("dw")[2]["kind"] == "rest" and store.markers("dw")[2]["ts_end"]
        assert [m["kind"] for m in done] == ["door_open", "door_close"] * 3 and all(m["ts_end"] and m["step_group"] for m in done)
        assert pg.is_visible("#cp-end a[href$='/learn']")
        # a started step that is aborted leaves nothing behind
        pg.click("#cp-again"); pg.click("#cp-scripts button:has-text('Open and close the door')"); pg.click("#cp-go"); pg.wait_for_selector("#cp-done:visible", timeout=15000)
        n = len(store.markers("dw")); pg.click("#cp-abort"); pg.wait_for_function("document.getElementById('cp-step').hidden")
        assert len(store.markers("dw")) == n - 1
        assert errors == []
        b.close()


def _login(pg, base):
    pg.goto(base + "/login?lang=en"); pg.fill("input[name=email]", MAIL); pg.fill("input[name=password]", PW); pg.click("button")


def _wizard_next(pg):
    if pg.is_visible("#wz-next"):                    # phone: one step at a time; desktop: everything is on one sheet
        pg.click("#wz-next")


@pytest.mark.parametrize("width", [1100, 390])
def test_device_lifecycle_firmware_and_learning_on_desktop_and_phone(server, width):
    """Add a device, read its firmware, edit, pause, learn from markers, delete: the same flow on both screen sizes."""
    from test_companion import door_markers, put_frames, series, door
    base, store = server
    key = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
    with sync_playwright_ctx() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": width, "height": 800}); errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        _login(pg, base)
        # --- add: type -> maker -> model -> connection
        pg.goto(base + "/devices?lang=en"); pg.click("#new-device"); pg.wait_for_selector("#device-dialog", state="visible")
        pg.click("#device-dialog label:has-text('Dryer')"); _wizard_next(pg)
        pg.click("#device-dialog label:has-text('AEG')"); _wizard_next(pg)
        pg.fill("#f-model", "T8DEE"); _wizard_next(pg)
        pg.fill("#f-name", "dry1"); pg.fill("#f-host", "dry1.lan"); pg.fill("#f-key", key)
        assert pg.is_visible("#save"); pg.click("#save")
        pg.wait_for_url("**/firmware/macs**")
        d = store.device("dry1")
        assert (d["type"], d["manufacturer"], d["model"], d["protocol"], d["host"], d["enabled"]) == ("dryer", "AEG", "T8DEE", "macs", "dry1.lan", True)
        assert store.db.execute("SELECT d.key FROM devices d JOIN sources s ON s.id=d.source_id WHERE s.name='dry1'").fetchone()[0] == key
        # --- firmware: both files, copy and download work
        assert pg.is_visible("text=macs-analysis.example.yaml") and pg.is_visible("text=macs_recorder.h")
        pg.click("button.copy >> nth=0"); pg.wait_for_selector("button.copy:has-text('Copied')")
        with pg.expect_download() as dl:
            pg.click("a[download] >> nth=1")
        assert dl.value.suggested_filename == "macs_recorder.h"
        assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0
        # --- edit: protocol stays fixed, model changes
        pg.goto(base + "/devices?lang=en"); pg.click(".edit-device >> nth=0"); pg.wait_for_selector("#device-dialog", state="visible")
        assert pg.input_value("#f-name") == "dry1" and pg.input_value("#f-model") == "T8DEE"
        while not pg.is_visible("#f-model"):          # phone: walk to the model step
            pg.click("#wz-next")
        pg.fill("#f-model", "T8DEE-2")
        while pg.is_visible("#wz-next"):
            pg.click("#wz-next")
        pg.click("#save"); pg.wait_for_url("**/devices")
        assert store.device("dry1")["model"] == "T8DEE-2"
        assert store.db.execute("SELECT d.key FROM devices d JOIN sources s ON s.id=d.source_id WHERE s.name='dry1'").fetchone()[0] == key           # an empty key field keeps the key
        # --- pause keeps the device, resume
        pg.goto(base + "/devices?lang=en"); pg.click("article.dev:has(a[href='/devices/dry1/delete']) details.more summary"); pg.click("form[action='/devices/dry1/enabled'] button")
        pg.wait_for_url("**/devices**"); assert store.device("dry1")["enabled"] is False
        # --- learn: companion data on the other device, accept a finding
        put_frames(store, "dw", series(door))
        for m in door_markers():
            store.add_marker("dw", m["kind"], m["label"], ts=m["ts"])
        pg.goto(base + "/s/dw/learn?lang=en")
        assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0
        pg.fill("form.accept input[name=meaning] >> nth=0", "Door state"); pg.click("form.accept button >> nth=0")
        pg.wait_for_url("**/learn#learned")
        assert [f["meaning"] for f in store.learned("dw")] == ["Door state"]
        # --- delete: typed name required
        pg.goto(base + "/devices?lang=en"); pg.click("article.dev:has(a[href='/devices/dry1/delete']) details.more summary"); pg.click("a[href='/devices/dry1/delete']")
        pg.fill("input[name=confirm]", "wrong"); pg.click("button.danger")
        assert store.device("dry1") is not None
        pg.fill("input[name=confirm]", "dry1"); pg.click("button.danger"); pg.wait_for_url("**/devices")
        assert store.device("dry1") is None and store.device("dw") is not None and len(store.markers("dw")) == 6
        assert errors == []
        b.close()


def sync_playwright_ctx():
    return pw.sync_playwright()
