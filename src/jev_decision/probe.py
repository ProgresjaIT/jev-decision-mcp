"""Authenticated MCP initialize + list_tools + health_check probe."""

import asyncio
import json
import os
import sys

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def probe():
    token = os.environ["MCP_TOKEN"]
    url = os.environ.get(
        "MCP_URL", f"http://127.0.0.1:{os.environ.get('PORT', '8765')}/mcp"
    )
    async with asyncio.timeout(12):
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}
        ) as http:
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    response = await session.call_tool(
                        "health_check",
                        {"check_api": os.environ.get("CHECK_API") == "1"},
                    )
                    data = response.structured_content
                    print(json.dumps({"tools": len(tools.tools), "health": data}))
                    return (
                        0
                        if not response.is_error
                        and len(tools.tools) == 10
                        and data["status"] == "approved"
                        else 1
                    )


def main():
    try:
        return asyncio.run(probe())
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
