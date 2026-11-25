import os

import pytest

from jev_decision.config import Settings
from jev_decision.service import DecisionService


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("JEV_LIVE_TEST") != "1",
    reason="Set JEV_LIVE_TEST=1 and TYPESAFE_API_KEY for a billable synthetic API test",
)
async def test_real_typesafe_batch(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "live.sqlite3"), mcp_token="local-test-only-" + "x" * 32
    )
    response = await DecisionService(settings).run(
        "batch_decisions",
        {"color": "blue", "quality": "excellent"},
        {
            "condition": {"type": "noul", "instructions": "Is the color blue?"},
            "color": {
                "type": "choice",
                "instructions": "What color is explicitly stated?",
                "criteria": {"blue": "Blue", "red": "Red"},
            },
            "quality": {
                "type": "score",
                "instructions": "Rate the explicitly stated quality",
                "criteria": ["poor", "average", "excellent"],
            },
        },
    )
    assert response["status"] in ("approved", "requires_review", "rejected"), response
    assert set(response["results"]) == {"condition", "color", "quality"}
    assert response["usage"]["input_tokens"] > 0
    print(
        "\nLIVE_METADATA",
        {
            k: response[k]
            for k in ("model", "status", "usage", "estimated_cost_usd", "elapsed_ms")
        },
    )
