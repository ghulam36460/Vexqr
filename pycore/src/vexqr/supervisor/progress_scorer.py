"""Progress Scorer (Supervisor sub-component 8.2.4).

Measures whether the sub-agent is producing new actionable findings or just
making noise. Fires LOW_PRODUCTIVITY after a window of calls with no novel
artifacts, and detects phase completion (diminishing returns) so the decomposer
can advance to the next phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import SubAgentState


@dataclass(slots=True)
class ProgressVerdict:
    productive: bool
    phase_complete: bool
    message: str | None = None


class ProgressScorer:
    def __init__(self, window: int) -> None:
        self._window = window

    def check(self, state: SubAgentState) -> ProgressVerdict:
        stale = state.calls_since_last_artifact

        if stale >= self._window and state.artifacts:
            return ProgressVerdict(
                productive=False,
                phase_complete=True,
                message=(
                    f"Phase '{state.current_phase}' has reached diminishing returns "
                    f"({stale} calls without a new finding, {len(state.artifacts)} artifacts collected). "
                    f"Advancing to the next phase."
                ),
            )

        if stale >= self._window:
            return ProgressVerdict(
                productive=False,
                phase_complete=False,
                message=(
                    f"This chain has not generated new findings in the last {stale} calls. "
                    f"Current known attack surface: {self._surface(state)}. "
                    f"Recommended next step: try a different technique or target rather than continuing this approach."
                ),
            )

        return ProgressVerdict(productive=True, phase_complete=False)

    def _surface(self, state: SubAgentState) -> str:
        counts: dict[str, int] = {}
        for a in state.artifacts:
            counts[a.kind] = counts.get(a.kind, 0) + 1
        if not counts:
            return "none yet"
        return ", ".join(f"{n} {k}{'s' if n > 1 else ''}" for k, n in counts.items())
