"""Embed only in a trusted writer process inaccessible to the agent's shell.

The writer callback MUST compare expected_version and write atomically. Policy,
identity and authorization callbacks come from the operator, never from an agent.
"""

import copy

from .server import RISK, instructions


class WriteGate:
    def __init__(self, decisions, policies, authorize, commit):
        self.decisions = decisions
        self.policies = dict(policies)
        self.authorize = authorize
        self.commit = commit

    async def execute(self, actor, proposed_action, trusted_context):
        action = copy.deepcopy(proposed_action)
        operation = action.get("operation")
        if operation not in self.policies or operation.lower().startswith("crm"):
            raise PermissionError("operation_not_allowed")
        if not self.authorize(actor, action):
            raise PermissionError("not_authorized")
        if type(action.get("expected_version")) is not int:
            raise PermissionError("version_required")
        policy = self.policies[operation]
        decision = await self.decisions.run(
            "validate_action",
            {"action": action, "context": trusted_context},
            {
                "valid": {
                    "type": "noul",
                    "instructions": instructions(
                        "Does this action satisfy ALL requirements?", policy
                    ),
                },
                "risk": {
                    "type": "choice",
                    "instructions": instructions(
                        "Classify risk of this action.", policy
                    ),
                    "criteria": RISK,
                },
            },
            risk_ids={"risk"},
        )
        if (
            decision.get("status") != "approved"
            or decision.get("meets_thresholds") is not True
        ):
            raise PermissionError("decision_did_not_approve")
        # Recheck revocable permissions after the network round trip.
        if not self.authorize(actor, action):
            raise PermissionError("authorization_revoked")
        execution = await self.commit(action)
        return {"decision_id": decision["decision_id"], "execution": execution}
