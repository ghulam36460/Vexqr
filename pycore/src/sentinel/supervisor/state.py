"""Per-sub-agent state tracked by the Supervisor monitor."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from ..core.types import Artifact, Phase, ToolCall

AgentStatus = Literal["active", "stalled", "looping", "budget_warning", "escalated", "complete"]

_WINDOW = 20


@dataclass(slots=True)
class SubAgentState:
    agent_id: str
    task_id: str
    current_phase: Phase
    tokens_budget: int
    tool_call_log: list[ToolCall] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set)
    tokens_used: int = 0
    loop_fire_count: int = 0
    calls_since_last_artifact: int = 0
    last_new_artifact_at: int = field(default_factory=lambda: int(time.time() * 1000))
    status: AgentStatus = "active"


def create_state(agent_id: str, task_id: str, phase: Phase, budget: int) -> SubAgentState:
    return SubAgentState(agent_id=agent_id, task_id=task_id, current_phase=phase, tokens_budget=budget)


def record_call(state: SubAgentState, call: ToolCall) -> None:
    state.tool_call_log.append(call)
    if len(state.tool_call_log) > _WINDOW:
        state.tool_call_log.pop(0)


def merge_artifacts(state: SubAgentState, incoming: list[Artifact]) -> list[Artifact]:
    """Merge new artifacts, returning only the genuinely novel ones."""
    novel: list[Artifact] = []
    for a in incoming:
        if a.key not in state._seen:
            state._seen.add(a.key)
            state.artifacts.append(a)
            novel.append(a)
    if novel:
        state.calls_since_last_artifact = 0
        state.last_new_artifact_at = int(time.time() * 1000)
    else:
        state.calls_since_last_artifact += 1
    return novel
