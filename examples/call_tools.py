"""Set MCP_URL and MCP_TOKEN. --all invokes billable synthetic examples."""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    calls = json.loads(Path(__file__).with_name("tools.json").read_text())
    if "--all" not in sys.argv:
        calls = [c for c in calls if c["name"] in ("health_check", "get_usage")]
    async with httpx2.AsyncClient(
        headers={"Authorization": "Bearer " + os.environ["MCP_TOKEN"]}
    ) as http:
        async with streamable_http_client(
            os.environ["MCP_URL"], http_client=http
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                for call in calls:
                    result = await session.call_tool(call["name"], call["arguments"])
                    print(
                        json.dumps(
                            {
                                "tool": call["name"],
                                "result": result.structured_content,
                                "is_error": result.is_error,
                            },
                            ensure_ascii=False,
                        )
                    )


if __name__ == "__main__":
    asyncio.run(main())
