import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class BudgetExceeded(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, tool TEXT NOT NULL,
                status TEXT NOT NULL, elapsed_ms REAL, input_tokens INTEGER,
                output_tokens INTEGER, cost REAL, reserved REAL NOT NULL,
                question_count INTEGER NOT NULL, error_code TEXT)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def reserve(self, decision_id, tool, count, settings):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, charged = db.execute(
                "SELECT count(*),coalesce(sum(coalesce(cost,reserved)),0) FROM decisions WHERE day=?",
                (day,),
            ).fetchone()
            if (
                calls >= settings.max_daily_calls
                or settings.reservation > settings.max_request_cost_usd
                or charged + settings.reservation > settings.daily_budget_usd
            ):
                raise BudgetExceeded()
            db.execute(
                "INSERT INTO decisions(id,day,tool,status,reserved,question_count) VALUES(?,?,?,?,?,?)",
                (decision_id, day, tool, "pending", settings.reservation, count),
            )

    def finish(self, result):
        usage = result.get("usage") or {}
        with self.connect() as db:
            db.execute(
                """UPDATE decisions SET status=?,elapsed_ms=?,input_tokens=?,output_tokens=?,
                cost=?,error_code=? WHERE id=?""",
                (
                    result["status"],
                    result["elapsed_ms"],
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                    result.get("estimated_cost_usd"),
                    result.get("error_code"),
                    result["decision_id"],
                ),
            )

    def usage(self):
        with self.connect() as db:
            values = db.execute("""SELECT count(*),coalesce(sum(input_tokens),0),
                coalesce(sum(output_tokens),0),coalesce(sum(cost),0),
                coalesce(sum(CASE WHEN cost IS NULL THEN reserved ELSE 0 END),0),
                coalesce(sum(CASE WHEN cost IS NULL THEN 1 ELSE 0 END),0) FROM decisions""").fetchone()
        return dict(
            zip(
                (
                    "calls",
                    "input_tokens",
                    "output_tokens",
                    "estimated_cost_usd",
                    "uncertain_reserved_usd",
                    "uncertain_calls",
                ),
                values,
            )
        )
