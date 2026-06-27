"""Heuristic worker agent.

A deterministic stand-in for a live AI client used for offline runs, demos and
tests. It deliberately exhibits the failure modes the Supervisor exists to catch
(repeating a scan, low-productivity tangents) so the supervision loop is
observable end-to-end. A real adapter swaps this for live model calls behind the
same WorkerAgent protocol.
"""

from __future__ import annotations

import re

from ..core.types import Target, ToolResult
from .base import AdapterContext, AgentDecision, DoneDecision, ToolCallDecision

_PHASE_PRIMARY: dict[str, str] = {
    "recon": "nmap",
    "enumeration": "gobuster",
    "vuln_scan": "nuclei",
    "exploit": "metasploit",
    "analysis": "ghidra",
    "post_exploit": "volatility",
    "report": "",
}


class HeuristicWorker:
    def __init__(self, target: Target, simulate_loop_on: str | None = None) -> None:
        self._target = target
        self._simulate_loop_on = simulate_loop_on
        self._calls_this_phase = 0
        self._last_phase = ""
        self._redirected = False

    async def next(self, ctx: AdapterContext) -> AgentDecision:
        if ctx.phase != self._last_phase:
            self._calls_this_phase = 0
            self._redirected = False
            self._last_phase = ctx.phase

        if ctx.feedback and re.search(r"LOOP_DETECTED|LOW_PRODUCTIVITY", ctx.feedback):
            self._redirected = True

        primary = _PHASE_PRIMARY.get(ctx.phase, "")
        if not primary or ctx.phase == "report":
            return DoneDecision(reason=f"phase '{ctx.phase}' produces a report, no tools to call")

        self._calls_this_phase += 1

        # Demonstrate a loop until the supervisor redirects.
        if self._simulate_loop_on == primary and not self._redirected and self._calls_this_phase <= 6:
            return ToolCallDecision(
                phase=ctx.phase, tool=primary, params={"host": self._target.host},
                description=f"{ctx.phase} scan with {primary}",
            )

        if self._calls_this_phase <= 2 and not self._redirected:
            return ToolCallDecision(
                phase=ctx.phase, tool=primary, params={"host": self._target.host},
                description=f"{ctx.phase} scan with {primary}",
            )

        return DoneDecision(reason=f"phase '{ctx.phase}' complete")

    def observe(self, _result: ToolResult) -> None:
        # A live agent would update its reasoning here.
        return None
