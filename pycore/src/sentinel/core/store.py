"""Persistent session + audit store (SQLite).

A lightweight, zero-server, cross-platform store for run history, discovered
artifacts, dispatched tool calls and supervisor interventions. The architecture
calls for SQLite as the registry/session/audit cache; this module provides that
for the orchestration layers.

It is append-mostly and best-effort: a storage failure must never break a live
run, so all writes are guarded. Subscribing to the event bus keeps the store
fully decoupled from the execution path.

NOTE: This is operational observability for the orchestration layers only. The
security team's audit log (tamper-evident, policy-driven) is a separate concern
owned outside this codebase.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..util.logger import get_logger
from .events import bus

_log = get_logger("store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    task_id      TEXT PRIMARY KEY,
    client       TEXT,
    goal         TEXT,
    target       TEXT,
    status       TEXT,
    risk_label   TEXT,
    risk_score   INTEGER,
    tokens_used  INTEGER,
    tokens_budget INTEGER,
    started_at   INTEGER,
    finished_at  INTEGER
);
CREATE TABLE IF NOT EXISTS artifacts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT,
    kind      TEXT,
    value     TEXT,
    source    TEXT,
    detail    TEXT,
    found_at  INTEGER
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT,
    tool      TEXT,
    route     TEXT,
    status    TEXT,
    token_cost INTEGER,
    duration_ms INTEGER,
    at        INTEGER
);
CREATE TABLE IF NOT EXISTS interventions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  TEXT,
    agent_id TEXT,
    reason   TEXT,
    message  TEXT,
    at       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_calls_task ON tool_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_interventions_task ON interventions(task_id);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(slots=True)
class RunRecord:
    task_id: str
    client: str
    goal: str
    target: str
    status: str
    risk_label: str
    risk_score: int
    tokens_used: int
    tokens_budget: int
    started_at: int
    finished_at: int


class SessionStore:
    """SQLite-backed run history + audit trail.

    Open with a path (default ``.sentinel/sessions.db``) or ``":memory:"`` for
    ephemeral use in tests. Call :meth:`subscribe` to wire it to the event bus
    so it records artifacts, tool calls and interventions automatically.
    """

    def __init__(self, path: str = ".sentinel/sessions.db") -> None:
        self._path = path
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._current: dict[str, str] = {}  # agent_id -> task_id (for interventions)

    # ---- lifecycle ---------------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def subscribe(self) -> "SessionStore":
        """Attach to the global event bus to record activity automatically."""
        bus.on("artifact:new", self._on_artifact)
        bus.on("tool:result", self._on_tool_result)
        bus.on("supervisor:feedback", self._on_feedback)
        bus.on("supervisor:escalate", self._on_escalate)
        return self

    # ---- writes ------------------------------------------------------------------

    def record_run(self, rec: RunRecord) -> None:
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rec.task_id, rec.client, rec.goal, rec.target, rec.status,
                    rec.risk_label, rec.risk_score, rec.tokens_used,
                    rec.tokens_budget, rec.started_at, rec.finished_at,
                ),
            )
            self._conn.commit()
        except Exception as exc:  # pragma: no cover - defensive
            _log.debug("record_run failed: %s", exc)

    def _on_artifact(self, payload: dict[str, Any]) -> None:
        a = payload.get("artifact")
        task_id = payload.get("taskId", "")
        agent_id = payload.get("agentId")
        if agent_id and task_id:
            self._current[agent_id] = task_id
        if a is None:
            return
        try:
            self._conn.execute(
                "INSERT INTO artifacts (task_id, kind, value, source, detail, found_at) VALUES (?,?,?,?,?,?)",
                (task_id, a.kind, a.value, a.source, a.detail, _now_ms()),
            )
        except Exception as exc:  # pragma: no cover - defensive
            _log.debug("artifact insert failed: %s", exc)

    def _on_tool_result(self, result: Any) -> None:
        try:
            self._conn.execute(
                "INSERT INTO tool_calls (task_id, tool, route, status, token_cost, duration_ms, at) VALUES (?,?,?,?,?,?,?)",
                (
                    getattr(result, "call_id", ""), result.tool, result.route,
                    result.status, result.token_cost, result.duration_ms, _now_ms(),
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive
            _log.debug("tool_call insert failed: %s", exc)

    def _on_feedback(self, payload: dict[str, Any]) -> None:
        self._record_intervention(payload.get("agentId", ""), payload.get("reason", ""), payload.get("message", ""))

    def _on_escalate(self, payload: dict[str, Any]) -> None:
        self._record_intervention(payload.get("agentId", ""), f"ESCALATE:{payload.get('reason', '')}", payload.get("summary", ""))

    def _record_intervention(self, agent_id: str, reason: str, message: str) -> None:
        try:
            self._conn.execute(
                "INSERT INTO interventions (task_id, agent_id, reason, message, at) VALUES (?,?,?,?,?)",
                (self._current.get(agent_id, ""), agent_id, reason, message, _now_ms()),
            )
        except Exception as exc:  # pragma: no cover - defensive
            _log.debug("intervention insert failed: %s", exc)

    # ---- reads -------------------------------------------------------------------

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT task_id, client, goal, target, status, risk_label, risk_score, "
            "tokens_used, tokens_budget, started_at, finished_at "
            "FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def run_detail(self, task_id: str) -> dict[str, Any]:
        run = self._conn.execute("SELECT * FROM runs WHERE task_id=?", (task_id,)).fetchone()
        arts = self._conn.execute(
            "SELECT kind, value, source, detail FROM artifacts WHERE task_id=?", (task_id,)
        ).fetchall()
        calls = self._conn.execute(
            "SELECT tool, route, status FROM tool_calls WHERE task_id=?", (task_id,)
        ).fetchall()
        return {
            "run": run,
            "artifacts": [{"kind": k, "value": v, "source": s, "detail": d} for k, v, s, d in arts],
            "tool_calls": [{"tool": t, "route": r, "status": st} for t, r, st in calls],
        }

    def to_json(self) -> str:
        return json.dumps(self.recent_runs(100), indent=2)
