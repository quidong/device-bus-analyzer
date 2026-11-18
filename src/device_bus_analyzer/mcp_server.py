"""MCP server (stdio) for Claude Desktop. Talks only to the analyzer's read-only HTTP API; every tool is a GET."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

TIMEOUT = 20.0


class Api:
    def __init__(self, base: str, token: str, client: httpx.Client | None = None):
        if not base or not token:
            raise RuntimeError("DBA_URL and DBA_TOKEN are required")
        self.c = client or httpx.Client(base_url=base.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)

    def get(self, path: str, **params: Any) -> Any:
        r = self.c.get(path, params={k: v for k, v in params.items() if v not in (None, "")})
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        return r.json()


def build_server(api: Api):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("device-bus-analyzer")

    @mcp.tool()
    def list_sources() -> str:
        """List recorded devices (name, protocol, number of bursts and frames, first/last timestamp as epoch seconds)."""
        return json.dumps(api.get("/api/sources"), indent=1)

    @mcp.tool()
    def get_findings(protocol: str) -> str:
        """Protocol specification with confirmed / assumed / unknown commands and their evidence (protocol: bshdbus or macs)."""
        return json.dumps(api.get(f"/api/spec/{protocol}"), indent=1)

    @mcp.tool()
    def command_overview(source: str) -> str:
        """All (destination, command) pairs seen on a device with counts, distinct values and decode status."""
        return json.dumps(api.get(f"/api/{source}/commands"), indent=1)

    @mcp.tool()
    def command_values(source: str, ds: str, cmd: str, limit: int = 50) -> str:
        """Distinct data values of one command (ds and cmd as hex, for example ds=25 cmd=2008) with counts."""
        return json.dumps(api.get(f"/api/{source}/commands/{ds}/{cmd}/values", limit=limit), indent=1)

    @mcp.tool()
    def timeline(source: str, since: str = "", until: str = "", limit: int = 500) -> str:
        """Value changes per command in time order. since/until: ISO 8601 (local time) or epoch seconds."""
        return json.dumps(api.get(f"/api/{source}/timeline", since=since, until=until, limit=limit), indent=1)

    @mcp.tool()
    def frames(source: str, ds: str = "", cmd: str = "", since: str = "", until: str = "", bad_only: bool = False,
               limit: int = 100, offset: int = 0) -> str:
        """Decoded telegrams, filterable by destination, command (hex) and time; bad_only returns CRC failures only."""
        return json.dumps(api.get(f"/api/{source}/frames", ds=ds, cmd=cmd, since=since, until=until,
                                  bad_only="true" if bad_only else "", limit=limit, offset=offset), indent=1)

    @mcp.tool()
    def raw_bursts(source: str, since: str = "", until: str = "", limit: int = 50, offset: int = 0) -> str:
        """Raw received bursts (hex) with sequence number and microsecond spacing, for protocol reverse engineering."""
        return json.dumps(api.get(f"/api/{source}/bursts", since=since, until=until, limit=limit, offset=offset), indent=1)

    @mcp.tool()
    def data_quality(source: str) -> str:
        """Frame counts, CRC errors, frames without ACK, board restarts and detected gaps in the recording."""
        return json.dumps(api.get(f"/api/{source}/quality"), indent=1)

    return mcp


def main() -> None:
    build_server(Api(os.environ.get("DBA_URL", ""), os.environ.get("DBA_TOKEN", ""))).run()


if __name__ == "__main__":
    main()
