"""Entry point bundled into the Claude Desktop extension (.mcpb). Dependencies: mcp, httpx (see requirements.txt)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from device_bus_analyzer.mcp_server import main  # noqa: E402

main()
