import pytest

from jev_decision.gate import WriteGate


class Decisions:
    def __init__(self, status):
        self.status = status

    async def run(self, *args, **kwargs):
        return {
            "status": self.status,
            "meets_thresholds": self.status == "approved",
            "decision_id": "id",
        }


@pytest.mark.parametrize("status", ["error", "rejected", "requires_review"])
async def test_gate_blocks_nonapproval(status):
    calls = []

    async def write(action):
        calls.append(action)

    gate = WriteGate(
        Decisions(status),
        {"radar.update": "Only reversible improvements"},
        lambda actor, action: True,
        write,
    )
    with pytest.raises(PermissionError):
        await gate.execute(
            "operator",
            {
                "operation": "radar.update",
                "expected_version": 1,
                "changes": {"prompt": "x"},
            },
            {"version": 1},
        )
    assert not calls


async def test_crm_never_write():
    async def write(action):
        raise AssertionError("must not execute")

    gate = WriteGate(
        Decisions("approved"), {"radar.update": "x"}, lambda actor, action: True, write
    )
    with pytest.raises(PermissionError):
        await gate.execute(
            "operator", {"operation": "crm.update", "expected_version": 1}, {}
        )


async def test_auth_is_independent():
    async def write(action):
        raise AssertionError("must not execute")

    gate = WriteGate(
        Decisions("approved"), {"radar.update": "x"}, lambda actor, action: False, write
    )
    with pytest.raises(PermissionError):
        await gate.execute(
            "operator", {"operation": "radar.update", "expected_version": 1}, {}
        )


async def test_approved_action_is_executed():
    calls = []

    async def write(action):
        calls.append(action)
        return "saved"

    gate = WriteGate(
        Decisions("approved"), {"radar.update": "x"}, lambda actor, action: True, write
    )
    r = await gate.execute(
        "operator", {"operation": "radar.update", "expected_version": 1}, {"version": 1}
    )
    assert r["execution"] == "saved" and len(calls) == 1


async def test_atomic_writer_rejects_replay(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "writer", Path(__file__).parents[1] / "examples/guarded_writer.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    writer = module.ConfigWriter(str(tmp_path / "config.db"))
    gate = module.make_gate(Decisions("approved"), writer)
    action = {
        "operation": "config.update",
        "resource": "demo",
        "expected_version": 1,
        "changes": {"prompt": "New"},
    }
    await gate.execute("trusted-demo-operator", action, writer.snapshot("demo"))
    with pytest.raises(PermissionError, match="stale_version"):
        await gate.execute("trusted-demo-operator", action, writer.snapshot("demo"))
    assert writer.snapshot("demo") == {"version": 2, "prompt": "New"}
