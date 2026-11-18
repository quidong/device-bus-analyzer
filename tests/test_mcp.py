import asyncio
import json

import httpx
import pytest
from conftest import raw1
from fastapi.testclient import TestClient

from device_bus_analyzer.config import Settings
from device_bus_analyzer.mcp_server import Api, build_server
from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.web import create_app


@pytest.fixture
def api(store):
    sid = store.source("dw", "bshdbus")
    store.ingest_line(sid, raw1(1, 1_000_000, build_frame(0x25, 0x2008, bytes([160]) + bytes(7))), 1_800_000_000.0)
    app = create_app(Settings(admin_email="a@b.de", admin_password="pw-pw-pw-pw", session_secret="s" * 32, api_token="T0K"), store)
    http = TestClient(app, base_url="http://analyzer", headers={"Authorization": "Bearer T0K"})
    return Api("http://analyzer", "T0K", client=http)


def call(mcp, name, **args):
    res = asyncio.run(mcp.call_tool(name, args))
    content = res[0] if isinstance(res, tuple) else res
    return json.loads(content[0].text)


def test_tools_are_registered_and_all_read_only(api):
    mcp = build_server(api)
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"list_sources", "get_findings", "command_overview", "command_values", "timeline", "frames", "raw_bursts", "data_quality"}


def test_tools_return_decoded_data(api):
    mcp = build_server(api)
    assert call(mcp, "list_sources")[0]["name"] == "dw"
    assert call(mcp, "frames", source="dw", cmd="2008")[0]["decoded"]["values"]["remaining_min"] == 160
    assert call(mcp, "command_overview", source="dw")[0]["n"] == 1
    assert call(mcp, "command_values", source="dw", ds="25", cmd="2008")[0]["n"] == 1
    assert call(mcp, "timeline", source="dw")[0]["cmd"] == 0x2008
    assert call(mcp, "raw_bursts", source="dw")[0]["seq"] == 1
    assert call(mcp, "data_quality", source="dw")["ok"] == 1
    assert call(mcp, "get_findings", protocol="bshdbus")["protocol"] == "bshdbus"


def test_errors_surface_as_exceptions(api):
    with pytest.raises(RuntimeError):
        api.get("/api/nobody/frames")
    with pytest.raises(RuntimeError):
        Api("", "")


def test_wrong_token_is_rejected(store):
    app = create_app(Settings(admin_email="a@b.de", admin_password="pw-pw-pw-pw", session_secret="s" * 32, api_token="T0K"), store)
    bad = Api("http://analyzer", "WRONG", client=TestClient(app, base_url="http://analyzer", headers={"Authorization": "Bearer WRONG"}))
    with pytest.raises(RuntimeError, match="401"):
        bad.get("/api/sources")
