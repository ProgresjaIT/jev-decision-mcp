import asyncio
import socket
from contextlib import asynccontextmanager

import httpx2
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from test_decisions import Provider

from jev_decision.server import create_app


class TypedProvider(Provider):
    async def evaluate(self, state, questions):
        self.calls += 1
        answers = {}
        for k, q in questions.items():
            if q["type"] == "noul":
                a = {"type": "noul", "noul": 0.99}
            elif q["type"] == "choice":
                keys = list(q["criteria"])
                a = {
                    "type": "choice",
                    "choice": keys[0],
                    "confidence": 0.99,
                    "probabilities": {x: 1.0 if x == keys[0] else 0.0 for x in keys},
                }
            else:
                n = len(q["criteria"])
                a = {
                    "type": "score",
                    "score": float(n - 1),
                    "confidence": 0.99,
                    "probabilities": {
                        str(i): 1.0 if i == n - 1 else 0.0 for i in range(n)
                    },
                    "legend": {str(i): v for i, v in enumerate(q["criteria"])},
                }
            answers[k] = a
        return {
            "model": "jev-1.14.0",
            "answers": answers,
            "usage": {"input_tokens": 30, "output_tokens": 10},
        }


@asynccontextmanager
async def running_app(settings, provider):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    sock.setblocking(False)
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings, provider), log_level="critical", access_log=False
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(200):
            if server.started:
                break
            if task.done():
                await task
            await asyncio.sleep(0.01)
        assert server.started
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5)
        sock.close()


async def test_real_http_mcp_all_tools(settings):
    provider = TypedProvider()
    common = {
        "context": "Synthetic facts",
        "goal": "Check quality",
        "criteria": "Evidence and reversible actions",
    }
    calls = {
        "make_decision": {**common, "options": {"keep": "Keep", "change": "Change"}},
        "evaluate_condition": common,
        "score_quality": {**common, "criteria": ["poor", "good", "excellent"]},
        "evaluate_risk": common,
        "compare_options": {**common, "options": {"old": "Current", "new": "Proposed"}},
        "classify_data": {
            **common,
            "categories": {"match": "Relevant", "other": "Unrelated"},
        },
        "validate_action": {
            **common,
            "action": {"operation": "update", "expected_version": 1},
        },
        "batch_decisions": {
            "context": "x",
            "questions": {
                "a": {"type": "noul", "instructions": "x"},
                "b": {
                    "type": "choice",
                    "instructions": "x",
                    "criteria": {"yes": "Yes", "no": "No"},
                },
            },
        },
        "get_usage": {},
        "health_check": {},
    }
    async with running_app(settings, provider) as url:
        async with httpx2.AsyncClient(
            headers={"Authorization": "Bearer " + "x" * 40}
        ) as http:
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    assert {t.name for t in listed.tools} == set(calls)
                    for name, args in calls.items():
                        response = await session.call_tool(name, args)
                        assert not response.is_error, (name, response)
                        data = response.structured_content
                        assert data["status"] == "approved", (name, data)
                    response = await session.call_tool(
                        "health_check", {"check_api": True}
                    )
                    assert response.structured_content["status"] == "approved"
    assert provider.calls == 9


async def test_auth_host_origin(settings):
    async with running_app(settings, TypedProvider()) as url:
        async with httpx2.AsyncClient() as http:
            assert (await http.post(url, json={})).status_code == 401
            auth = {"Authorization": "Bearer " + "x" * 40}
            assert (
                await http.post(
                    url, headers={**auth, "Origin": "https://evil.example"}, json={}
                )
            ).status_code == 403
            assert (
                await http.post(url, headers={**auth, "Host": "evil.example"}, json={})
            ).status_code == 400
