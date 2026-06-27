"""Layer 5 — AI Supervisor Engine (the core differentiator).

Cross-cutting meta-layer that observes every sub-agent in real time and steers
it WITHOUT executing tools itself. After each tool result it runs:
  - artifact merge + progress scoring
  - loop detection (pre-call)
  - token budget evaluation
and, when a failure mode is detected, formats an ACTIONABLE corrective feedback
message routed through the agent's native channel. It also manages human
escalation gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..core.config import SentinelConfig
from ..core.events import bus
from ..core.types import Artifact, Phase, SourceClient, ToolCall, ToolResult
from .escalation import EscalationManager, EscalationRequest, HumanGate
from .feedback_injector import Feedback, FeedbackInjector
from .loop_detector import LoopDetector
from .progress_scorer import ProgressScorer
from .state import SubAgentState, create_state, merge_artifacts, record_call
from .token_budget import TokenBudgetManager

InterventionKind = Literal["continue", "redirect", "wrap_up", "stop", "advance_phase", "escalate"]


@dataclass(slots=True)
class Intervention:
    kind: InterventionKind
    novel_artifacts: list[Artifact] = field(default_factory=list)
    feedback: str | None = None
    reason: str | None = None


class Supervisor:
    def __init__(self, config: SentinelConfig, client: SourceClient, human_gate: HumanGate) -> None:
        self._config = config
        self._client = client
        self._states: dict[str, SubAgentState] = {}
        self._loop = LoopDetector(config.supervisor.loop_threshold)
        self._progress = ProgressScorer(config.supervisor.productivity_window)
        self._budget = TokenBudgetManager(config.supervisor.token_safety_margin)
        self._injector = FeedbackInjector()
        self._escalation = EscalationManager(human_gate)

    def register(self, agent_id: str, task_id: str, phase: Phase, token_budget: int) -> None:
        self._states[agent_id] = create_state(agent_id, task_id, phase, token_budget)
        bus.emit("phase:enter", {"taskId": task_id, "phase": phase})

    def set_phase(self, agent_id: str, phase: Phase, token_budget: int) -> None:
        s = self._states.get(agent_id)
        if not s:
            return
        s.current_phase = phase
        s.tokens_budget = token_budget
        s.tokens_used = 0
        s.calls_since_last_artifact = 0
        s.loop_fire_count = 0
        s.status = "active"
        bus.emit("phase:enter", {"taskId": s.task_id, "phase": phase})

    def before_call(self, agent_id: str, call: ToolCall) -> Intervention | None:
        state = self._states.get(agent_id)
        if not state:
            return None
        record_call(state, call)

        verdict = self._loop.check(state, call)
        if verdict.looping:
            state.loop_fire_count += 1
            state.status = "looping"
            if state.loop_fire_count >= self._config.supervisor.loop_escalation_limit:
                return Intervention(kind="escalate", reason="LOOP_ESCALATION", feedback=verdict.message)
            _, payload = self._injector.inject(
                self._client, Feedback(agent_id, "LOOP_DETECTED", verdict.message or "")
            )
            return Intervention(kind="redirect", reason="LOOP_DETECTED", feedback=payload)
        return None

    def after_result(self, agent_id: str, result: ToolResult) -> Intervention:
        state = self._states.get(agent_id)
        if not state:
            return Intervention(kind="continue")

        novel = merge_artifacts(state, result.artifacts)
        for a in novel:
            bus.emit("artifact:new", {"taskId": state.task_id, "agentId": agent_id, "artifact": a})

        # 1. Token budget takes precedence — it can force a wrap-up.
        b = self._budget.consume(state, result.token_cost)
        bus.emit(
            "budget:level",
            {"agentId": agent_id, "level": b.level, "tokensUsed": state.tokens_used, "tokensBudget": state.tokens_budget},
        )
        if b.stop:
            state.status = "budget_warning"
            _, payload = self._injector.inject(self._client, Feedback(agent_id, b.level.upper(), b.message or ""))
            return Intervention(kind="wrap_up", reason=b.level, feedback=payload, novel_artifacts=novel)
        if b.message:
            self._injector.inject(self._client, Feedback(agent_id, b.level.upper(), b.message))

        # 2. Progress scoring — phase completion or low-productivity pivot.
        p = self._progress.check(state)
        if p.phase_complete:
            bus.emit("phase:complete", {"taskId": state.task_id, "phase": state.current_phase})
            return Intervention(kind="advance_phase", reason="PHASE_COMPLETE", feedback=p.message, novel_artifacts=novel)
        if not p.productive and p.message:
            _, payload = self._injector.inject(self._client, Feedback(agent_id, "LOW_PRODUCTIVITY", p.message))
            return Intervention(kind="redirect", reason="LOW_PRODUCTIVITY", feedback=payload, novel_artifacts=novel)

        state.status = "active"
        return Intervention(kind="continue", novel_artifacts=novel)

    async def request_human_gate(
        self,
        agent_id: str,
        reason: str,
        summary: str,
    ) -> Literal["approve", "deny"]:
        s = self._states.get(agent_id)
        if s:
            s.status = "escalated"
        return await self._escalation.escalate(EscalationRequest(agent_id=agent_id, reason=reason, summary=summary))  # type: ignore[arg-type]

    def state(self, agent_id: str) -> SubAgentState | None:
        return self._states.get(agent_id)

    def all_artifacts(self, agent_id: str) -> list[Artifact]:
        s = self._states.get(agent_id)
        return s.artifacts if s else []

    def tokens_used(self, agent_id: str) -> int:
        s = self._states.get(agent_id)
        return s.tokens_used if s else 0
