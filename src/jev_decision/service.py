import asyncio
import json
import math
import re
import time
import uuid

from .provider import TypeSafeProvider
from .store import BudgetExceeded, Store

SECRET_KEY = re.compile(
    r"(?i)^(password|passwd|secret|api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|private[_-]?key)$"
)
SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+\S+|-----BEGIN .*PRIVATE KEY-----|(?:api[_-]?key|password|secret)\s*[=:]\s*\S+)"
)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE = re.compile(r"(?<!\w)\+\d[\d ()-]{7,}\d(?!\w)")


def sanitize(value, secrets=(), depth=0):
    if depth > 32:
        raise ValueError("input_too_deep")
    if isinstance(value, dict):
        if any(SECRET_KEY.match(str(k)) for k in value):
            raise ValueError("secret_detected")
        return {
            sanitize(str(k), secrets, depth + 1): sanitize(v, secrets, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize(v, secrets, depth + 1) for v in value]
    if isinstance(value, str):
        if SECRET_TEXT.search(value) or any(s and s in value for s in secrets):
            raise ValueError("secret_detected")
        return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", value))
    if value is None or isinstance(value, (int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("invalid_number")
        return value
    raise ValueError("invalid_input")


def probability(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("invalid_probability")
    return value


def validate_question(q):
    if (
        set(q) - {"type", "instructions", "criteria"}
        or not isinstance(q.get("instructions"), str)
        or not q["instructions"].strip()
    ):
        raise ValueError("invalid_question")
    kind, criteria = q.get("type"), q.get("criteria")
    if kind == "choice":
        if (
            not isinstance(criteria, dict)
            or not 2 <= len(criteria) <= 255
            or not all(
                isinstance(k, str) and k and isinstance(v, str)
                for k, v in criteria.items()
            )
        ):
            raise ValueError("invalid_choices")
    elif kind == "score":
        if (
            not isinstance(criteria, list)
            or not 2 <= len(criteria) <= 10
            or not all(isinstance(v, str) and v for v in criteria)
        ):
            raise ValueError("invalid_rubric")
    elif kind == "noul":
        if criteria is not None and (
            not isinstance(criteria, dict)
            or set(criteria) != {"true", "false"}
            or not all(isinstance(v, str) for v in criteria.values())
        ):
            raise ValueError("invalid_noul_criteria")
    else:
        raise ValueError("unsupported_question_type")


def interpret(answer, question, settings, risk=False):
    kind = question["type"]
    if answer.get("type") != kind:
        raise ValueError("answer_type_mismatch")
    result = {
        "type": kind,
        "confidence": None,
        "probabilities": None,
        "risk_level": None,
    }
    if kind == "noul":
        p = probability(answer["noul"])
        status = (
            "approved"
            if p >= settings.min_probability
            else "rejected"
            if p <= settings.noul_reject_threshold
            else "requires_review"
        )
        result.update(value=p, probability_true=p)
    else:
        confidence = probability(answer["confidence"])
        probs = answer["probabilities"]
        expected = (
            set(question["criteria"])
            if kind == "choice"
            else {str(i) for i in range(len(question["criteria"]))}
        )
        if not isinstance(probs, dict) or set(probs) != expected:
            raise ValueError("invalid_distribution_keys")
        if abs(sum(probability(p) for p in probs.values()) - 1) > 0.001:
            raise ValueError("invalid_distribution_sum")
        result.update(confidence=confidence, probabilities=probs)
        if kind == "choice":
            value = answer["choice"]
            if value not in expected or probs[value] + 0.001 < max(probs.values()):
                raise ValueError("invalid_choice")
            status = (
                "approved"
                if confidence >= settings.min_confidence
                and probs[value] >= settings.min_probability
                else "requires_review"
            )
            if risk:
                result["risk_level"] = value
                if status == "approved" and value != "low":
                    status = (
                        "rejected"
                        if value in ("high", "critical")
                        else "requires_review"
                    )
        else:
            value = answer["score"]
            n = len(expected) - 1
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= n
            ):
                raise ValueError("invalid_score")
            if abs(value - sum(int(k) * p for k, p in probs.items())) > 0.02:
                raise ValueError("inconsistent_score")
            legend = answer["legend"]
            if legend != {str(i): v for i, v in enumerate(question["criteria"])}:
                raise ValueError("invalid_legend")
            result["legend"] = legend
            status = (
                "requires_review"
                if confidence < settings.min_confidence
                else "approved"
                if value / n >= settings.score_min_fraction
                else "rejected"
            )
        result["value"] = value
    result.update(status=status, meets_thresholds=status == "approved")
    return result


class DecisionService:
    def __init__(self, settings, provider=None):
        self.settings = settings
        self.store = Store(settings.db_path)
        self.provider = provider or TypeSafeProvider(settings)

    async def run(self, tool, context, questions, risk_ids=()):
        started = time.monotonic()
        result = {
            "decision_id": str(uuid.uuid4()),
            "tool": tool,
            "status": "error",
            "meets_thresholds": False,
            "results": {},
            "usage": None,
            "estimated_cost_usd": None,
            "cost_source": "configured_rates_not_provider_invoice",
            "model": None,
        }
        reserved = False
        try:
            if (
                not isinstance(context, (str, dict, list))
                or not isinstance(questions, dict)
                or not 1 <= len(questions) <= self.settings.max_questions
            ):
                raise ValueError("invalid_request")
            if not all(isinstance(k, str) and k for k in questions):
                raise ValueError("invalid_question_id")
            for q in questions.values():
                validate_question(q)
            payload = {"state": context, "questions": questions}
            encoded = json.dumps(payload, allow_nan=False).encode()
            if len(encoded) > self.settings.max_input_bytes:
                raise ValueError("input_too_large")
            sanitized = sanitize(
                payload,
                (
                    self.settings.typesafe_api_key.get_secret_value(),
                    self.settings.mcp_token.get_secret_value(),
                ),
            )
            # Never silently change option ids/rubrics; these define the response contract.
            if sanitized["questions"] != questions:
                raise ValueError("personal_data_in_question")
            if not self.settings.typesafe_api_key.get_secret_value():
                raise ValueError("missing_typesafe_key")
            self.store.reserve(
                result["decision_id"], tool, len(questions), self.settings
            )
            reserved = True
            async with asyncio.timeout(self.settings.timeout_seconds):
                response = await self.provider.evaluate(sanitized["state"], questions)
            usage = response["usage"]
            if any(
                type(usage.get(k)) is not int or usage[k] < 0
                for k in ("input_tokens", "output_tokens")
            ):
                raise ValueError("invalid_usage")
            result["usage"] = {k: usage[k] for k in ("input_tokens", "output_tokens")}
            result["estimated_cost_usd"] = (
                usage["input_tokens"] * self.settings.input_usd_per_million
                + usage["output_tokens"] * self.settings.output_usd_per_million
            ) / 1_000_000
            if not isinstance(response.get("model"), str) or not response["model"]:
                raise ValueError("invalid_model")
            result["model"] = response["model"]
            if set(response["answers"]) != set(questions):
                raise ValueError("answer_keys_mismatch")
            parsed = {
                k: interpret(response["answers"][k], q, self.settings, k in risk_ids)
                for k, q in questions.items()
            }
            statuses = {r["status"] for r in parsed.values()}
            result["status"] = (
                "rejected"
                if "rejected" in statuses
                else "requires_review"
                if "requires_review" in statuses
                else "approved"
            )
            result["results"] = parsed
            if result["estimated_cost_usd"] > self.settings.reservation:
                result.update(
                    status="requires_review", error_code="reservation_exceeded"
                )
            result["meets_thresholds"] = result["status"] == "approved"
        except BudgetExceeded:
            result.update(status="requires_review", error_code="budget_or_call_limit")
        except Exception as exc:
            # Exception messages may include submitted state or provider response bodies.
            safe_errors = {
                "invalid_request",
                "invalid_question_id",
                "invalid_question",
                "invalid_choices",
                "invalid_rubric",
                "invalid_noul_criteria",
                "unsupported_question_type",
                "input_too_large",
                "secret_detected",
                "personal_data_in_question",
                "missing_typesafe_key",
                "input_too_deep",
                "invalid_number",
                "invalid_input",
            }
            code = (
                str(exc)
                if type(exc) is ValueError and str(exc) in safe_errors
                else type(exc).__name__
            )
            result.update(
                status="error", error_code=code, meets_thresholds=False, results={}
            )
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
        if reserved:
            try:
                self.store.finish(result)
            except Exception:
                result.update(
                    status="error",
                    meets_thresholds=False,
                    error_code="history_write_failed",
                    results={},
                )
        return result
