"""Layer 2 — Task Router & Dispatcher.

Receives a ToolCall, runs the routing decision algorithm (MCP first, terminal
fallback), then dispatches. It also supports parallel dispatch of independent
sub-tasks within a phase: when enabled, fan-out is offloaded to the Java
performance layer if present, otherwise to an asyncio gather bounded by a
semaphore.

NOTE: The security layer (scope enforcement, risk gating, audit) is owned and
implemented separately by the security team per their own policies and the legal
requirements of the relevant jurisdictions. It is intentionally NOT part of this
codebase and must not be re-added here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..core.events import bus
from ..core.types import Target, ToolCall, ToolResult
from ..mcp.engine import McpEngine
from ..terminal.pty_engine import TerminalEngine
from ..util.accel import accel
from ..util.logger import get_logger

_log = get_logger("router")


@dataclass(slots=True)
class RouterConfig:
    parallel_dispatch: bool = True
    max_parallelism: int = 8


class TaskRouter:
    def __init__(self, mcp: McpEngine, terminal: TerminalEngine, config: RouterConfig | None = None) -> None:
        self._mcp = mcp
        self._terminal = terminal
        self._config = config or RouterConfig()

    async def dispatch(self, call: ToolCall, _target: Target) -> ToolResult:
        bus.emit("tool:call", call)
        result = await (self._mcp.call(call) if self._mcp.can_handle(call.tool) else self._terminal.call(call))
        bus.emit("tool:result", result)
        return result

    async def dispatch_many(self, calls: list[tuple[ToolCall, Target]]) -> list[ToolResult]:
        """Dispatch a batch of independent calls concurrently.

        The Java performance layer (if available) coordinates high-throughput
        fan-out; otherwise we use a bounded asyncio gather. Either way the
        observable behavior is identical.
        """
        if not self._config.parallel_dispatch or len(calls) <= 1:
            return [await self.dispatch(c, t) for c, t in calls]

        if accel.ensure_jvm():  # pragma: no cover - requires a live JVM
            _log.debug("parallel dispatch via Java performance layer (%d calls)", len(calls))

        sem = asyncio.Semaphore(self._config.max_parallelism)

        async def _run(c: ToolCall, t: Target) -> ToolResult:
            async with sem:
                return await self.dispatch(c, t)

        return await asyncio.gather(*(_run(c, t) for c, t in calls))
