import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_initializes_with_only_provider_key(tmp_path):
    (tmp_path / '.env').write_text('MCP_TOKEN=short\nTYPESAFE_API_KEY=\n')
    env = {k: v for k, v in os.environ.items() if k not in {'MCP_TOKEN', 'MODEL', 'TYPESAFE_API_KEY'}}
    env.update(
        TYPESAFE_API_KEY='synthetic-key',
        PYTHONPATH=str(Path(__file__).parents[1] / 'src'),
        DB_PATH=str(tmp_path / 'history.sqlite3'),
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=['-m', 'jev_decision.server'],
        env=env,
        cwd=str(tmp_path),
    )
    async with asyncio.timeout(15):
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 10
                result = await session.call_tool('health_check', {})
                assert result.structured_content['status'] == 'approved'
                assert result.structured_content['api_checked'] is False
