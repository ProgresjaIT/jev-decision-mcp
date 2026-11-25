import json

import httpx2
import pytest
from typesafe_sdk import AsyncTypeSafeClient

from jev_decision import provider as module
from jev_decision.service import DecisionService


@pytest.mark.parametrize("status", [401, 429, 500, 529])
async def test_sdk_http_errors_fail_closed(settings, monkeypatch, status):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx2.Response(status, json={"detail": "synthetic error"})

    original = AsyncTypeSafeClient
    monkeypatch.setattr(
        module,
        "AsyncTypeSafeClient",
        lambda **kw: original(**kw, transport=httpx2.MockTransport(handle)),
    )
    result = await DecisionService(settings).run(
        "evaluate_condition", "synthetic", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert result["status"] == "error" and not result["meets_thresholds"]
    assert len(seen) == 1  # No SDK retries that could duplicate cost.
    assert str(seen[0].url) == "https://api.typesafe.ai/v1/systemone"


async def test_sdk_real_serialization(settings, monkeypatch):
    def handle(request):
        body = json.loads(request.content)
        assert body["model"] == "jev-1.14.0"
        assert body["questions"] == {"q": {"type": "noul", "instructions": "x"}}
        return httpx2.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {"q": {"type": "noul", "noul": 0.98}},
                "usage": {"input_tokens": 12, "output_tokens": 2},
            },
        )

    original = AsyncTypeSafeClient
    monkeypatch.setattr(
        module,
        "AsyncTypeSafeClient",
        lambda **kw: original(**kw, transport=httpx2.MockTransport(handle)),
    )
    result = await DecisionService(settings).run(
        "evaluate_condition", "synthetic", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert result["status"] == "approved"
    assert result["usage"]["input_tokens"] == 12


async def test_sdk_mixed_batch(settings, monkeypatch):
    def handle(request):
        return httpx2.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    "c": {
                        "type": "choice",
                        "choice": "a",
                        "confidence": 1.0,
                        "probabilities": {"a": 1.0, "b": 0.0},
                    },
                    "s": {
                        "type": "score",
                        "score": 1.0,
                        "confidence": 1.0,
                        "probabilities": {"0": 0.0, "1": 1.0},
                        "legend": {"0": "bad", "1": "good"},
                    },
                    "n": {"type": "noul", "noul": 0.99},
                },
                "usage": {"input_tokens": 20, "output_tokens": 12},
            },
        )

    original = AsyncTypeSafeClient
    monkeypatch.setattr(
        module,
        "AsyncTypeSafeClient",
        lambda **kw: original(**kw, transport=httpx2.MockTransport(handle)),
    )
    r = await DecisionService(settings).run(
        "batch_decisions",
        "synthetic",
        {
            "c": {
                "type": "choice",
                "instructions": "x",
                "criteria": {"a": "A", "b": "B"},
            },
            "s": {"type": "score", "instructions": "x", "criteria": ["bad", "good"]},
            "n": {"type": "noul", "instructions": "x"},
        },
    )
    assert r["status"] == "approved"
    assert r["results"]["s"]["legend"] == {"0": "bad", "1": "good"}
