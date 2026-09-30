from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .catalog import destination_advisory, search_activities, search_lodging

mcp = FastMCP(
    "travel-buddy-tools",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
)
mcp.tool()(search_activities)
mcp.tool()(search_lodging)
mcp.tool()(destination_advisory)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
