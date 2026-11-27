"""Real-browser check of the device overview, the device dialog and the responsive layout (skipped when Playwright or Chrome is not installed)."""
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
def test_overview_layout_and_pages_without_overflow(server, width):
    base, store = server
    sid = store.source_by_name("dw")["id"]
    for i, cmd in enumerate([0x1010, 0x1010, 0x1010, 0x7777]):        # 0x7777 is not in the spec: 1 of 2 telegram types is analysed at most
        store.db.execute("INSERT INTO frames(source_id, ts, ds, cmd, data, crc_ok) VALUES(?,?,?,?,?,1)", (sid, time.time() - 10 + i, 0x17, cmd, b"\x00\x01"))
    store.db.commit()
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": width, "height": 800}); errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base + "/login?lang=en"); pg.fill("input[name=email]", MAIL); pg.fill("input[name=password]", PW); pg.click("button")
        for path in ("/", "/devices", "/s/dw/runs", "/s/dw/learn", "/s/dw/timeline", "/firmware/bshdbus", "/help", "/backup", "/mcp", "/s/dw/homeassistant"):
            for lang in ("en", "fr"):               # fr: the longest strings
                pg.goto(base + path + "?lang=" + lang)
                assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0, (path, width, lang)
        pg.goto(base + "/devices?lang=en")
        # getting started and the device cards do not touch
        onb, cards = pg.locator("section.onboarding").bounding_box(), pg.locator("div.cards").bounding_box()
        assert cards["y"] - (onb["y"] + onb["height"]) >= 16
        # every action is an icon button of the same size, with a tooltip and no text
        boxes = [pg.locator("article.dev .ibtn").nth(i).bounding_box() for i in range(pg.locator("article.dev .ibtn").count())]
        assert len(boxes) >= 4 and len({(round(x["width"]), round(x["height"])) for x in boxes}) == 1
        assert all(pg.locator("article.dev .ibtn").nth(i).inner_text().strip() == "" for i in range(len(boxes)))
        assert pg.locator("article.dev details").count() == 0
        # analysed share instead of the telegram count
        txt = pg.inner_text("article.dev .analysed dd")
        assert "%" in txt and int(txt.split("%")[0].strip()) <= 50 and pg.locator("article.dev .analysed progress").count() == 1
        # icon and name open the device
        pg.click("article.dev a.devlink .name"); pg.wait_for_url("**/s/dw/runs")
        pg.goto(base + "/devices?lang=en"); pg.click("article.dev a.devlink .tile"); pg.wait_for_url("**/s/dw/runs")
        assert pg.locator("a[href$='/companion']").count() == 0
        # prompts on the AI connection page: device name filled in, copy works
        pg.goto(base + "/mcp?lang=en")
        assert pg.locator(".prompts pre").count() == 6 and '"dw"' in pg.inner_text("#mcp-p2")
        pg.click(".prompts button.copy >> nth=0"); pg.wait_for_selector(".prompts button.copy:has-text('Copied')")
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
        if pg.is_visible("#wz-next"):                    # phone: the model is required before the next step
            pg.click("#wz-next"); assert pg.is_visible("#f-model") and not pg.is_visible("#f-name")
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
        pg.goto(base + "/devices?lang=en"); pg.click("article.dev:has(a[href='/devices/dry1/delete']) .ibtn.edit-device"); pg.wait_for_selector("#device-dialog", state="visible")
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
        pg.goto(base + "/devices?lang=en"); pg.click("form[action='/devices/dry1/enabled'] button.ibtn")
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
        pg.goto(base + "/devices?lang=en"); pg.click("a.ibtn[href='/devices/dry1/delete']")
        pg.fill("input[name=confirm]", "wrong"); pg.click("button.danger")
        assert store.device("dry1") is not None
        pg.fill("input[name=confirm]", "dry1"); pg.click("button.danger"); pg.wait_for_url("**/devices")
        assert store.device("dry1") is None and store.device("dw") is not None and len(store.markers("dw")) == 6
        assert errors == []
        b.close()


def sync_playwright_ctx():
    return pw.sync_playwright()


@pytest.mark.parametrize("width", [1100, 390])
def test_dialog_offers_every_brand_and_bus_and_remembers_own_models(server, width):
    base, store = server
    store.save_device("old", "bshdbus", "washer", "Miele", "WWD 120", "old.lan")
    store.remember_classification("washer", "Miele", "WWD 120", "bshdbus")
    store.delete_device("old")                                         # an own model outlives its device
    with sync_playwright_ctx() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": width, "height": 900}); errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        _login(pg, base)
        pg.goto(base + "/devices?lang=de"); pg.click("#new-device"); pg.wait_for_selector("#device-dialog", state="visible")
        pg.click("#device-dialog label:has-text('Waschmaschine')"); _wizard_next(pg)
        for brand in ("Bosch", "Siemens", "Neff", "Electrolux", "AEG", "Miele"):          # every brand for every type
            assert pg.is_visible(f"#device-dialog label.opt:has-text('{brand}')"), brand
        assert pg.is_visible("#f-proto")
        pg.click("#device-dialog label.opt:has-text('AEG')"); assert pg.input_value("#f-proto") == "macs"
        pg.click("#device-dialog label.opt:has-text('Bosch')"); assert pg.input_value("#f-proto") == "bshdbus"
        pg.select_option("#f-proto", "macs")                               # own choice of bus is kept
        assert pg.input_value("#f-proto") == "macs" and pg.inner_text("#decoder-name") == "macs"
        pg.click("#device-dialog label.opt:has-text('Miele')"); assert pg.input_value("#f-proto") == "bshdbus"
        _wizard_next(pg)
        assert pg.is_visible("#model-chips button:has-text('WWD 120')")
        pg.click("#model-chips button:has-text('WWD 120')"); assert pg.input_value("#f-model") == "WWD 120"
        _wizard_next(pg)
        pg.fill("#f-name", "wm"); pg.fill("#f-host", "wm.lan"); pg.click("#save"); pg.wait_for_url("**/firmware/bshdbus**")
        d = store.device("wm")
        assert (d["type"], d["manufacturer"], d["model"], d["protocol"]) == ("washer", "Miele", "WWD 120", "bshdbus")
        assert errors == []
        b.close()


def test_login_survives_a_second_tab_and_an_expired_token(server):
    base, store = server
    with sync_playwright_ctx() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = b.new_context(); a = ctx.new_page(); other = ctx.new_page()
        a.goto(base + "/login?lang=de"); other.goto(base + "/login?lang=de")          # the second tab must not break the first
        a.fill("input[name=email]", MAIL); a.fill("input[name=password]", PW); a.click("button"); a.wait_for_url(base + "/")
        ctx.clear_cookies()                                                              # signed out; the login page then lies around for long (cookies cleared: language falls back to the browser)
        a.goto(base + "/login?lang=de"); ctx.clear_cookies()                            # its token cookie is gone as well
        a.fill("input[name=email]", MAIL); a.fill("input[name=password]", PW); a.click("button")
        assert "open for too long" in a.inner_text("p.err") and a.input_value("input[name=email]") == MAIL
        assert "bad CSRF" not in a.content()
        a.fill("input[name=password]", PW); a.click("button"); a.wait_for_url(base + "/")  # second try works
        b.close()
