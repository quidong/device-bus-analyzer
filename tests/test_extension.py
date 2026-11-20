"""Runs the Node MCP extension against a real analyzer instance (skipped without node / node_modules)."""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from conftest import raw1

from device_bus_analyzer.config import Settings
from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.web import create_app

EXT = Path(__file__).resolve().parent.parent / "extension"
pytestmark = pytest.mark.skipif(not shutil.which("node") or not (EXT / "node_modules").exists(),
                                reason="node or extension/node_modules missing (run npm ci in extension/)")


@pytest.fixture
def live(store):
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 1_000_000, build_frame(0x17, 0x1013, b"\x01")), 1_799_999_990.0)
    store.ingest_line(sid, raw1(2, 2_000_000, build_frame(0x25, 0x2008, bytes([160]) + bytes(7)) + b"\x2a"), 1_800_000_000.0)
    app = create_app(Settings(admin_email="a@b.de", admin_password="pw-pw-pw-pw", session_secret="s" * 32, api_token="T0K", knowledge_url="https://127.0.0.1:9/none.json"), store)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


def test_node_extension_smoke(live):
    r = subprocess.run(["node", "test/smoke.mjs"], cwd=EXT, env={**os.environ, "DBA_URL": live, "DBA_TOKEN": "T0K"},
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "smoke OK" in r.stdout, r.stdout + r.stderr


def test_manifest_is_consistent_with_server():
    m = json.loads((EXT / "manifest.json").read_text())
    src = (EXT / "server" / "index.js").read_text()
    assert m["server"]["type"] == "node" and (EXT / m["server"]["entry_point"]).exists()
    for t in m["tools"]:
        assert f'"{t["name"]}"' in src
    assert m["user_config"]["token"]["sensitive"] is True
    assert set(m["user_config"]) == {"url", "token", "ca_file"} and not m["user_config"]["ca_file"]["required"]
    env = m["server"]["mcp_config"]["env"]
    assert env == {"DBA_URL": "${user_config.url}", "DBA_TOKEN": "${user_config.token}", "DBA_CA_FILE": "${user_config.ca_file}"}
