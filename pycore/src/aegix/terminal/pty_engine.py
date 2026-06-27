"""Layer 4 — Terminal Automation Engine.

Wraps ANY CLI security tool so an AI client can use it as if it were a real MCP
server (the "mock MCP interface"). For interactive tools (msfconsole,
sqlmap --wizard) a real PTY is required; production uses ``ptyprocess`` here.

To keep the platform runnable offline, this engine uses ``subprocess`` for
non-interactive tools and falls back to the simulator in dry-run mode. The
interface mirrors ``McpEngine.call`` so the router and supervisor cannot tell
which route executed a tool.
"""

from __future__ import annotations

import subprocess
import time

from ..core.types import ToolCall, ToolResult
from ..util.ids import estimate_tokens
from ..util.logger import get_logger
from .argv import build_argv
from .installer import AutoInstaller
from .parser import parse_tool_output
from .simulator import simulate_tool_output

_log = get_logger("pty-engine")


class TerminalEngine:
    def __init__(self, installer: AutoInstaller, dry_run: bool) -> None:
        self._installer = installer
        self._dry_run = dry_run

    def can_handle(self, _tool: str) -> bool:
        # L4 is the universal fallback — it can attempt any tool.
        return True

    async def call(self, call: ToolCall) -> ToolResult:
        start = time.time()
        tool = call.tool.lower()

        install = self._installer.ensure(tool)
        if not install.installed:
            return ToolResult(
                call_id=call.call_id,
                tool=tool,
                route="terminal",
                status="error",
                errors=[install.error or "tool unavailable", install.manual_hint or ""],
                duration_ms=int((time.time() - start) * 1000),
            )

        status: str = "ok"
        if self._dry_run or install.already_present is False:
            raw = simulate_tool_output(tool, call.params)
        else:
            try:
                raw = self._exec(tool, call)
            except TimeoutError:
                raw, status = "", "timeout"
            except Exception:
                raw, status = "", "error"

        artifacts = parse_tool_output(tool, raw) if status == "ok" else []
        _log.info("terminal call '%s' -> %s, %d artifacts", tool, status, len(artifacts))

        return ToolResult(
            call_id=call.call_id,
            tool=tool,
            route="terminal",
            status=status,  # type: ignore[arg-type]
            artifacts=artifacts,
            output=raw,
            errors=[] if status == "ok" else [f"tool '{tool}' exited with {status}"],
            token_cost=estimate_tokens(raw),
            duration_ms=int((time.time() - start) * 1000),
        )

    def _exec(self, tool: str, call: ToolCall) -> str:
        argv = build_argv(tool, call.params)
        timeout_ms = int(call.params.get("timeoutMs", call.params.get("timeout_ms", 120_000)))
        try:
            proc = subprocess.run(
                [tool, *argv],
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError from exc
        return proc.stdout or proc.stderr
