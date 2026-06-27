"""Feedback Injector (Supervisor sub-component 8.2.6).

Delivers corrective feedback to a sub-agent through ITS OWN native channel:
  * API clients  -> mid-conversation system message
  * CLI clients  -> stdin write to the subprocess
  * MCP agents   -> tool_result with isError=true
  * IDE agents   -> extension / MCP error channel

Every message is ACTIONABLE: (1) what was detected, (2) what it means,
(3) a specific recommended next action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..core.events import bus
from ..core.types import SourceClient
from ..util.logger import get_logger

_log = get_logger("feedback")

InjectionChannel = Literal["system_message", "stdin", "tool_error", "ide_message"]


@dataclass(slots=True)
class Feedback:
    agent_id: str
    reason: str
    message: str


def channel_for(client: SourceClient) -> InjectionChannel:
    if client in ("claude_api", "gemini_cli", "custom"):
        return "system_message"
    if client in ("claude_code", "codex"):
        return "stdin"
    if client in ("copilot", "gitlab_duo", "cursor"):
        return "ide_message"
    return "tool_error"


class FeedbackInjector:
    def inject(self, client: SourceClient, fb: Feedback) -> tuple[InjectionChannel, str]:
        channel = channel_for(client)
        payload = f"[SUPERVISOR:{fb.reason}] {fb.message}"
        _log.info("inject -> %s via %s: %s", client, channel, fb.reason)
        bus.emit("supervisor:feedback", {"agentId": fb.agent_id, "reason": fb.reason, "message": fb.message})
        return channel, payload
