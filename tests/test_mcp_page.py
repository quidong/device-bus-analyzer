"""The connection page for Claude: session only, shows address and token, says plainly that ChatGPT is not supported."""
from fastapi.testclient import TestClient
from test_companion import MAIL, PW, login

from device_bus_analyzer.config import Settings
from device_bus_analyzer.store import Store
from device_bus_analyzer.web import create_app


def make(tmp_path, token):
    return TestClient(create_app(Settings(admin_email=MAIL, admin_password=PW, session_secret="s" * 32, api_token=token), Store(tmp_path / "a.sqlite")),
                      follow_redirects=False, base_url="http://analyzer.lan:8089")


def test_page_needs_a_session_not_the_api_token(tmp_path):
    c = make(tmp_path, "tok-secret-1")
    assert c.get("/mcp").status_code == 303
    assert c.get("/mcp", headers={"Authorization": "Bearer tok-secret-1"}).status_code == 303


def test_page_shows_address_token_download_and_chatgpt_note(tmp_path):
    c = make(tmp_path, "tok-secret-1")
    login(c)
    html = c.get("/mcp?lang=en").text
    assert "http://analyzer.lan:8089" in html and "tok-secret-1" in html and 'data-target="mcp-token"' in html
    assert "raw/main/device-bus-analyzer.mcpb" in html and "ChatGPT cannot use this extension" in html
    assert 'href="/mcp"' in c.get("/devices").text


def test_page_without_token_explains_what_to_set(tmp_path):
    c = make(tmp_path, "")
    login(c)
    html = c.get("/mcp?lang=de").text
    assert "DBA_API_TOKEN" in html and "mcp-token" not in html
