"""Core domain types — the internal lingua franca of the whole platform.

Every AI client adapter (L1) normalizes its native protocol into a ``TaskObject``;
every layer below operates on these shared shapes. Adding a new AI client means
writing one adapter, with zero changes elsewhere.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

SourceClient = Literal[
    "claude_api",
    "claude_code",
    "gemini_cli",
    "copilot",
    "gitlab_duo",
    "cursor",
    "codex",
    "custom",
]

Phase = Literal[
    "recon",
    "enumeration",
    "vuln_scan",
    "exploit",
    "analysis",
    "post_exploit",
    "report",
]

PHASES: tuple[Phase, ...] = (
    "recon",
    "enumeration",
    "vuln_scan",
    "exploit",
    "analysis",
    "post_exploit",
    "report",
)

ArtifactKind = Literal[
    "host",
    "port",
    "service",
    "cve",
    "path",
    "credential",
    "domain",
    "finding",
    "tech",
    "email",
    "secret",
]

RouteKind = Literal["mcp", "terminal", "internal"]

ToolStatus = Literal["ok", "error", "timeout", "blocked"]


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(slots=True)
class Target:
    host: str
    ports: list[int] | None = None
    paths: list[str] | None = None


@dataclass(slots=True)
class TaskConstraints:
    scope_id: str = "default"
    max_tokens: int = 200_000
    risk_level: Literal["low", "medium", "high"] = "medium"
    timeout_ms: int = 600_000


@dataclass(slots=True)
class TaskContext:
    session_id: str
    prior_findings: list["Artifact"] = field(default_factory=list)
    active_phase: Phase = "recon"


@dataclass(slots=True)
class TaskObject:
    task_id: str
    source_client: SourceClient
    request_type: Phase
    natural_input: str
    target: Target
    context: TaskContext
    constraints: TaskConstraints
    tools_hint: list[str] | None = None


@dataclass(slots=True)
class Artifact:
    """A single atomic, novel piece of intelligence discovered during a run."""

    kind: ArtifactKind
    value: str
    source: str | None = None
    detail: str | None = None
    discovered_at: int = field(default_factory=_now_ms)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


@dataclass(slots=True)
class ToolCall:
    call_id: str
    agent_id: str
    task_id: str
    phase: Phase
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str | None = None


@dataclass(slots=True)
class ToolResult:
    call_id: str
    tool: str
    route: RouteKind
    status: ToolStatus
    artifacts: list[Artifact] = field(default_factory=list)
    output: str = ""
    errors: list[str] = field(default_factory=list)
    token_cost: int = 0
    duration_ms: int = 0
    is_supervisor_feedback: bool = False


@dataclass(slots=True)
class ResultObject:
    task_id: str
    source_client: SourceClient
    status: Literal["complete", "partial", "aborted"]
    summary: str
    artifacts: list[Artifact]
    phases_completed: list[Phase]
    tokens_used: int
    tokens_budget: int
    started_at: int
    finished_at: int

    def to_native(self) -> dict[str, Any]:
        """Generic, client-agnostic serialization (adapters reshape per protocol)."""
        return {
            "task_id": self.task_id,
            "client": self.source_client,
            "status": self.status,
            "summary": self.summary,
            "findings": [
                {"type": a.kind, "value": a.value, "detail": a.detail, "source": a.source}
                for a in self.artifacts
            ],
            "phases_completed": list(self.phases_completed),
            "tokens": {"used": self.tokens_used, "budget": self.tokens_budget},
            "duration_ms": self.finished_at - self.started_at,
        }
