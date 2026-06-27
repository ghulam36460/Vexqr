"""Token Budget Manager (Supervisor sub-component 8.2.5).

Real-time token tracking with progressive interventions. A safety margin is
applied so the effective ceiling is below the raw budget, leaving headroom for
the final summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .state import SubAgentState

BudgetLevel = Literal["monitor", "watch", "warn", "critical", "force_wrap", "exhausted"]


@dataclass(slots=True)
class BudgetVerdict:
    level: BudgetLevel
    fraction: float
    stop: bool
    message: str | None = None


class TokenBudgetManager:
    def __init__(self, safety_margin: float) -> None:
        self._margin = safety_margin

    def consume(self, state: SubAgentState, tokens: int) -> BudgetVerdict:
        state.tokens_used += tokens
        return self.evaluate(state)

    def evaluate(self, state: SubAgentState) -> BudgetVerdict:
        effective = state.tokens_budget * (1 - self._margin)
        fraction = state.tokens_used / effective if effective > 0 else 1.0

        if fraction >= 1:
            return BudgetVerdict(
                "exhausted",
                fraction,
                True,
                "Token budget exhausted. Tool call chain terminated. Return all findings collected so far "
                "and mark the task partial-complete, listing what was not investigated.",
            )
        if fraction >= 0.9:
            return BudgetVerdict(
                "force_wrap",
                fraction,
                True,
                "Token budget at 90%. Stop all new tool calls. Summarize all findings discovered so far and "
                "mark the task as partial-complete. Include what was not investigated.",
            )
        if fraction >= 0.8:
            return BudgetVerdict(
                "critical",
                fraction,
                False,
                "You are at 85% of your task token budget. Complete the current step only. "
                "Begin preparing a partial findings summary.",
            )
        if fraction >= 0.7:
            return BudgetVerdict(
                "warn",
                fraction,
                False,
                "You are at 70% of your task token budget. Prioritize the highest-impact remaining step. "
                "Skip low-confidence branches. Do not open new sub-investigations.",
            )
        if fraction >= 0.5:
            return BudgetVerdict("watch", fraction, False)
        return BudgetVerdict("monitor", fraction, False)
