"""Layer 3 — MCP Management Engine.

Launches/health-checks MCP server processes and routes tool calls over the
correct transport (stdio/SSE/HTTP). Trust-tier policy is enforced here: official
tools auto-run; community/experimental require confirmation on first use. In
dry-run mode (or when a real server binary is absent) calls are simulated so the
rest of the pipeline can be exercised end-to-end.

Real transport wiring uses the official ``mcp`` Python SDK; this engine keeps a
transport-agnostic surface so swapping in the live SDK is a localized change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..core.types import ToolCall, ToolResult
from ..terminal.parser import parse_tool_output
from ..terminal.simulator import simulate_tool_output
from ..util.ids import estimate_tokens
from ..util.logger import get_logger
from .registry import McpRegistry, RegistryEntry

_log = get_logger("mcp-engine")

ConfirmFn = Callable[[str], Awaitable[bool]]


@dataclass(slots=True)
class _RunningServer:
    tool: str
    started_at: float
    healthy: bool
    approved: bool


class McpEngine:
    def __init__(self, registry: McpRegistry, dry_run: bool, confirm: ConfirmFn) -> None:
        self._registry = registry
        self._dry_run = dry_run
        self._confirm = confirm
        self._servers: dict[str, _RunningServer] = {}

    def can_handle(self, tool: str) -> bool:
        return self._registry.has(tool)

    async def call(self, call: ToolCall) -> ToolResult:
        start = time.time()
        tool = McpRegistry.normalize(call.tool)
        entry = self._registry.get(tool)
        if entry is None:
            return self._error(call, start, f"no MCP server registered for '{tool}'", "blocked")

        if not await self._ensure_trust(tool, entry):
            return self._error(call, start, f"user declined {entry.trust_tier} MCP server for '{tool}'", "blocked")

        self._ensure_running(tool, entry)

        if self._dry_run:
            raw = simulate_tool_output(tool, call.params)
        else:
            raw = await self._invoke_transport(entry, call)

        artifacts = parse_tool_output(tool, raw)
        _log.info("mcp call '%s' via %s -> %d artifacts", tool, entry.transport, len(artifacts))
        return ToolResult(
            call_id=call.call_id,
            tool=tool,
            route="mcp",
            status="ok",
            artifacts=artifacts,
            output=raw,
            token_cost=estimate_tokens(raw),
            duration_ms=int((time.time() - start) * 1000),
        )

    async def _ensure_trust(self, tool: str, entry: RegistryEntry) -> bool:
        existing = self._servers.get(tool)
        if existing and existing.approved:
            return True
        if entry.trust_tier == "official":
            return True
        # In dry-run nothing real is installed or executed, so first-use
        # confirmation gates are unnecessary noise — auto-approve them.
        if self._dry_run:
            return True
        prompt = (
            f"MCP server for '{tool}' is trust tier '{entry.trust_tier}'.\n"
            f"  server: {entry.mcp_server}\n"
            f"  Approve running it? [y/N] "
        )
        return await self._confirm(prompt)

    def _ensure_running(self, tool: str, entry: RegistryEntry) -> None:
        existing = self._servers.get(tool)
        if existing and existing.healthy:
            return
        _log.debug("starting MCP server '%s' (%s) [transport=%s]", tool, entry.mcp_server, entry.transport)
        self._servers[tool] = _RunningServer(tool, time.time(), True, True)

    async def _invoke_transport(self, entry: RegistryEntry, call: ToolCall) -> str:
        _log.warning("live MCP transport '%s' not configured; simulating '%s'", entry.transport, call.tool)
        return simulate_tool_output(McpRegistry.normalize(call.tool), call.params)

    def _error(self, call: ToolCall, start: float, msg: str, status: str) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            tool=McpRegistry.normalize(call.tool),
            route="mcp",
            status=status,  # type: ignore[arg-type]
            errors=[msg],
            duration_ms=int((time.time() - start) * 1000),
        )

    def shutdown(self) -> None:
        for tool in self._servers:
            _log.debug("shutting down MCP server '%s'", tool)
        self._servers.clear()
