"""Trusted-process example. Never expose this database or policies to an agent."""

import sqlite3

from jev_decision.gate import WriteGate


class ConfigWriter:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS config (id TEXT PRIMARY KEY, version INTEGER NOT NULL, prompt TEXT NOT NULL)"
            )
            db.execute(
                "INSERT OR IGNORE INTO config VALUES ('demo',1,'Original prompt')"
            )

    def snapshot(self, resource):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT version,prompt FROM config WHERE id=?", (resource,)
            ).fetchone()
        if row is None:
            raise PermissionError("resource_not_allowed")
        return {"version": row[0], "prompt": row[1]}

    async def commit(self, action):
        changes = action.get("changes", {})
        if (
            set(changes) != {"prompt"}
            or not isinstance(changes["prompt"], str)
            or not 1 <= len(changes["prompt"]) <= 4000
        ):
            raise PermissionError("invalid_changes")
        with sqlite3.connect(self.path) as db:
            count = db.execute(
                "UPDATE config SET prompt=?,version=version+1 WHERE id=? AND version=?",
                (changes["prompt"], action["resource"], action["expected_version"]),
            ).rowcount
            if count != 1:
                raise PermissionError("stale_version")
        return {"saved": True, "version": action["expected_version"] + 1}


def make_gate(decisions, writer):
    return WriteGate(
        decisions,
        {
            "config.update": "Only change the prompt to improve precision without loss of recall. Require supporting evaluation evidence and a rollback plan."
        },
        lambda actor, action: (
            actor == "trusted-demo-operator" and action.get("resource") == "demo"
        ),
        writer.commit,
    )
