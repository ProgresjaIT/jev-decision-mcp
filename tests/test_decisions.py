import pytest

from jev_decision.service import DecisionService


class Provider:
    def __init__(self, answer=None, error=None):
        self.answer = answer or {"type": "noul", "noul": 0.98}
        self.error = error
        self.calls = 0

    async def evaluate(self, state, questions):
        self.calls += 1
        if self.error:
            raise self.error
        return {
            "model": "jev-1.14.0",
            "answers": {k: self.answer for k in questions},
            "usage": {"input_tokens": 20, "output_tokens": 3},
        }


@pytest.mark.parametrize(
    "p,status", [(0.98, "approved"), (0.5, "requires_review"), (0.02, "rejected")]
)
async def test_noul_thresholds(settings, p, status):
    service = DecisionService(settings, Provider({"type": "noul", "noul": p}))
    result = await service.run(
        "evaluate_condition",
        "safe context",
        {"q": {"type": "noul", "instructions": "Is this true?"}},
    )
    assert result["status"] == status
    assert result["results"]["q"]["confidence"] is None
    assert result["usage"]["input_tokens"] == 20


@pytest.mark.parametrize(
    "answer",
    [
        {"type": "noul", "noul": float("nan")},
        {"type": "noul", "noul": 1.1},
        {"type": "noul"},
        {
            "type": "choice",
            "choice": "invented",
            "probabilities": {"a": 1.0},
            "confidence": 1.0,
        },
    ],
)
async def test_malformed_never_approves(settings, answer):
    r = await DecisionService(settings, Provider(answer)).run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error"


async def test_timeout_and_unknown_cost(settings):
    service = DecisionService(settings, Provider(error=TimeoutError()))
    r = await service.run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error"
    assert service.store.usage()["uncertain_calls"] == 1


async def test_budget_persists(settings):
    settings.daily_budget_usd = 0.003
    p = Provider(error=TimeoutError())
    s = DecisionService(settings, p)
    await s.run("evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}})
    s = DecisionService(settings, p)
    r = await s.run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "requires_review"
    assert p.calls == 1


async def test_history_has_no_customer_data(settings):
    s = DecisionService(settings, Provider())
    await s.run(
        "evaluate_condition",
        "CUSTOMER_PRIVATE_DATA",
        {"q": {"type": "noul", "instructions": "x"}},
    )
    assert b"CUSTOMER_PRIVATE_DATA" not in open(settings.db_path, "rb").read()


async def test_batch_is_one_call(settings):
    p = Provider()
    s = DecisionService(settings, p)
    r = await s.run(
        "batch_decisions",
        {"x": "y"},
        {str(i): {"type": "noul", "instructions": "x"} for i in range(3)},
    )
    assert len(r["results"]) == 3
    assert p.calls == 1


async def test_secret_blocked_before_network(settings):
    p = Provider()
    s = DecisionService(settings, p)
    r = await s.run(
        "evaluate_condition",
        {"api_key": "secret"},
        {"q": {"type": "noul", "instructions": "x"}},
    )
    assert r["status"] == "error"
    assert p.calls == 0


@pytest.mark.parametrize(
    "confidence,p,status",
    [
        (0.1, 0.99, "requires_review"),
        (0.99, 0.6, "requires_review"),
        (0.99, 0.99, "approved"),
    ],
)
async def test_choice_thresholds(settings, confidence, p, status):
    a = {
        "type": "choice",
        "choice": "yes",
        "confidence": confidence,
        "probabilities": {"yes": p, "no": 1 - p},
    }
    r = await DecisionService(settings, Provider(a)).run(
        "make_decision",
        "x",
        {
            "q": {
                "type": "choice",
                "instructions": "x",
                "criteria": {"yes": "Yes", "no": "No"},
            }
        },
    )
    assert r["status"] == status


async def test_concurrent_budget_atomic(settings):
    import asyncio

    settings.daily_budget_usd = 0.003
    p = Provider(error=TimeoutError())
    a = DecisionService(settings, p)
    b = DecisionService(settings, p)
    results = await asyncio.gather(
        *(
            s.run(
                "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
            )
            for s in (a, b)
        )
    )
    assert sorted(r["status"] for r in results) == ["error", "requires_review"]
    assert p.calls == 1


async def test_timeout_enforced(settings):
    import asyncio

    class Slow(Provider):
        async def evaluate(self, *args):
            await asyncio.sleep(1)

    settings.timeout_seconds = 0.01
    r = await DecisionService(settings, Slow()).run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error" and r["error_code"] == "TimeoutError"


async def test_unknown_answer_keys(settings):
    class Wrong(Provider):
        async def evaluate(self, *args):
            return {
                "model": "jev-1.14.0",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": {},
            }

    r = await DecisionService(settings, Wrong()).run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error"


async def test_pii_redacted(settings):
    class Inspect(Provider):
        async def evaluate(self, state, questions):
            assert "test@example.org" not in state
            assert "+48123456789" not in state
            return await super().evaluate(state, questions)

    r = await DecisionService(settings, Inspect()).run(
        "evaluate_condition",
        "test@example.org +48123456789",
        {"q": {"type": "noul", "instructions": "x"}},
    )
    assert r["status"] == "approved"


@pytest.mark.parametrize(
    "risk,status",
    [
        ("low", "approved"),
        ("medium", "requires_review"),
        ("high", "rejected"),
        ("critical", "rejected"),
    ],
)
async def test_risk_policy(settings, risk, status):
    from jev_decision.server import RISK

    a = {
        "type": "choice",
        "choice": risk,
        "confidence": 1.0,
        "probabilities": {k: float(k == risk) for k in RISK},
    }
    r = await DecisionService(settings, Provider(a)).run(
        "evaluate_risk",
        "x",
        {"risk": {"type": "choice", "instructions": "x", "criteria": RISK}},
        risk_ids={"risk"},
    )
    assert r["status"] == status
    assert r["results"]["risk"]["risk_level"] == risk


@pytest.mark.parametrize(
    "value,confidence,status",
    [(0.0, 1.0, "rejected"), (2.0, 1.0, "approved"), (2.0, 0.1, "requires_review")],
)
async def test_score_policy(settings, value, confidence, status):
    a = {
        "type": "score",
        "score": value,
        "confidence": confidence,
        "probabilities": {str(i): float(i == value) for i in range(3)},
        "legend": {"0": "poor", "1": "good", "2": "excellent"},
    }
    r = await DecisionService(settings, Provider(a)).run(
        "score_quality",
        "x",
        {
            "q": {
                "type": "score",
                "instructions": "x",
                "criteria": ["poor", "good", "excellent"],
            }
        },
    )
    assert r["status"] == status


async def test_missing_key_no_network(settings):
    from pydantic import SecretStr

    settings.typesafe_api_key = SecretStr("")
    p = Provider()
    r = await DecisionService(settings, p).run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error" and r["error_code"] == "missing_typesafe_key"
    assert p.calls == 0


async def test_input_and_batch_limits(settings):
    p = Provider()
    s = DecisionService(settings, p)
    r = await s.run(
        "evaluate_condition",
        "x" * (settings.max_input_bytes + 1),
        {"q": {"type": "noul", "instructions": "x"}},
    )
    assert r["status"] == "error"
    r = await s.run(
        "batch_decisions",
        "x",
        {
            str(i): {"type": "noul", "instructions": "x"}
            for i in range(settings.max_questions + 1)
        },
    )
    assert r["status"] == "error" and p.calls == 0


async def test_usage_survives_service_restart(settings):
    a = DecisionService(settings, Provider())
    await a.run("evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}})
    b = DecisionService(settings, Provider())
    assert b.store.usage()["calls"] == 1
    assert b.store.usage()["input_tokens"] == 20


async def test_history_failure_blocks_approval(settings, monkeypatch):
    a = DecisionService(settings, Provider())

    def fail(result):
        raise OSError("disk full")

    monkeypatch.setattr(a.store, "finish", fail)
    r = await a.run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "error" and not r["meets_thresholds"]


@pytest.mark.parametrize("limit", ["cost", "calls"])
async def test_request_limits(settings, limit):
    p = Provider()
    s = DecisionService(settings, p)
    if limit == "cost":
        settings.max_request_cost_usd = 0.000001
    else:
        settings.max_daily_calls = 1
        await s.run(
            "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
        )
    before = p.calls
    r = await s.run(
        "evaluate_condition", "x", {"q": {"type": "noul", "instructions": "x"}}
    )
    assert r["status"] == "requires_review" and p.calls == before
