"""Layer 1 — AI Client Adapter contract.

Each supported AI client implements these protocols. Internally everything
speaks TaskObject / ResultObject; the adapter is the only place that knows a
client's native protocol (REST, JSON-RPC, MCP, VS Code API, etc.).

The ``WorkerAgent`` abstraction represents the actual AI doing the work: given
the current findings, it decides the next tool call (or signals done). In
production this is the live Claude/Gemini/etc. call; for offline runs a heuristic
stand-in implements the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..core.types import Artifact, Phase, ResultObject, TaskObject, ToolResult


@dataclass(slots=True)
class AdapterContext:
    phase: Phase
    tool_whitelist: list[str]
    findings: list[Artifact] = field(default_factory=list)
    feedback: str | None = None


@dataclass(slots=True)
class ToolCallDecision:
    phase: Phase
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str | None = None


@dataclass(slots=True)
class DoneDecision:
    reason: str


AgentDecision = ToolCallDecision | DoneDecision


@runtime_checkable
class WorkerAgent(Protocol):
    async def next(self, ctx: AdapterContext) -> AgentDecision: ...
    def observe(self, result: ToolResult) -> None: ...


@runtime_checkable
class ClientAdapter(Protocol):
    id: str

    def normalize(self, input_text: str, target: str, overrides: dict[str, Any] | None = None) -> TaskObject: ...
    def create_worker(self, task: TaskObject) -> WorkerAgent: ...
    def format_result(self, result: ResultObject) -> Any: ...
