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
        for path in ("/", "/devices", "/s/dw/companion", "/s/dw/learn", "/s/dw/timeline", "/firmware/bshdbus"):
            pg.goto(base + path + "?lang=en")
            assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0, (path, width)
        pg.goto(base + "/s/dw/companion?lang=en")
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
        for i in range(6):
            assert pg.is_visible("#cp-go") and not pg.is_visible("#cp-done")
            pg.click("#cp-go"); pg.wait_for_selector("#cp-done:visible"); pg.click("#cp-done")
            if i < 5:
                pg.wait_for_selector("#cp-go:visible")
        pg.wait_for_selector("#cp-end:visible")
        done = store.markers("dw")[2:]
        assert [m["kind"] for m in done] == ["door_open", "door_close"] * 3 and all(m["ts_end"] and m["step_group"] for m in done)
        assert pg.is_visible("#cp-end a[href$='/learn']")
        # a started step that is aborted leaves nothing behind
        pg.click("#cp-again"); pg.click("#cp-scripts button:has-text('Open and close the door')"); pg.click("#cp-go"); pg.wait_for_selector("#cp-done:visible")
        n = len(store.markers("dw")); pg.click("#cp-abort"); pg.wait_for_function("document.getElementById('cp-step').hidden")
        assert len(store.markers("dw")) == n - 1
        assert errors == []
        b.close()
