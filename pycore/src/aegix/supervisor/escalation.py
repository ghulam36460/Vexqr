"""Human Escalation Manager (Supervisor sub-component 8.2.7).

Conditions that pause a sub-agent and hand control to a human:
  1. HIGH_RISK tool request
  2. Loop escalation (loop fired N times, auto-correction failed)
  3. Novel critical finding
  4. Sub-agent contradiction of the phase plan

Scope-boundary escalation is handled by the separately-owned security layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from ..core.events import bus
from ..util.logger import get_logger

_log = get_logger("escalation")

EscalationReason = Literal[
    "HIGH_RISK", "LOOP_ESCALATION", "CRITICAL_FINDING", "PLAN_CONTRADICTION"
]


@dataclass(slots=True)
class EscalationRequest:
    agent_id: str
    reason: EscalationReason
    summary: str
    options: list[str] = field(default_factory=lambda: ["approve", "deny"])


# A host app implements this to actually ask a human.
HumanGate = Callable[[EscalationRequest], Awaitable[Literal["approve", "deny"]]]


async def deny_gate(_req: EscalationRequest) -> Literal["approve", "deny"]:
    return "deny"


class EscalationManager:
    def __init__(self, gate: HumanGate) -> None:
        self._gate = gate

    async def escalate(self, req: EscalationRequest) -> Literal["approve", "deny"]:
        _log.warning("escalating to human: %s (agent %s)", req.reason, req.agent_id)
        bus.emit("supervisor:escalate", {"agentId": req.agent_id, "reason": req.reason, "summary": req.summary})
        decision = await self._gate(req)
        _log.info("human decision for %s: %s", req.reason, decision)
        return decision
