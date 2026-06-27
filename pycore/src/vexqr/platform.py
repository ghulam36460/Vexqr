"""Public entry point — assembles the layers into a ready-to-run platform.

Construct a ``Vexqr`` with a config and a set of host callbacks (MCP confirm +
human gate), then ``await app.run(goal, target)``.

The security layer (scope, risk gating, audit) is intentionally omitted: it is
owned and implemented separately by the security team according to their own
policies and the laws of the relevant jurisdictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .adapters.base import ClientAdapter
from .adapters.generic import GenericAdapter
from .core.config import VexqrConfig, load_config
from .core.orchestrator import Orchestrator
from .core.reporter import risk_score
from .core.store import RunRecord, SessionStore
from .core.types import ResultObject, SourceClient
from .mcp.engine import McpEngine
from .mcp.registry import McpRegistry
from .router.router import RouterConfig, TaskRouter
from .supervisor.escalation import EscalationRequest, deny_gate
from .supervisor.supervisor import Supervisor
from .terminal.installer import AutoInstaller
from .terminal.pty_engine import TerminalEngine


async def _default_confirm(_prompt: str) -> bool:
    return False


@dataclass(slots=True)
class VexqrOptions:
    config: VexqrConfig | None = None
    client: SourceClient = "custom"
    dry_run: bool | None = None
    confirm_mcp: Callable[[str], Awaitable[bool]] = _default_confirm
    human_gate: Callable[[EscalationRequest], Awaitable[Any]] = deny_gate
    simulate_loop_on: str | None = None
    adapter: ClientAdapter | None = None
    store: SessionStore | None = None


class Vexqr:
    def __init__(self, options: VexqrOptions | None = None) -> None:
        opts = options or VexqrOptions()
        self.config = opts.config or load_config()
        if opts.dry_run is not None:
            self.config.dry_run = opts.dry_run

        client = opts.client

        # L3 — MCP.
        registry = McpRegistry.load(self.config.registry_path)
        self._mcp = McpEngine(registry, self.config.dry_run, opts.confirm_mcp)

        # L4 — Terminal.
        installer = AutoInstaller(self.config.dry_run)
        terminal = TerminalEngine(installer, self.config.dry_run)

        # L2 — Router.
        router = TaskRouter(
            self._mcp,
            terminal,
            RouterConfig(self.config.parallel_dispatch, self.config.max_parallelism),
        )

        # L5 — Supervisor.
        supervisor = Supervisor(self.config, client, opts.human_gate)

        # L1 — Adapter.
        self._adapter = opts.adapter or GenericAdapter(client, opts.simulate_loop_on)

        # Optional persistent session/audit store.
        self._store = opts.store
        if self._store is not None:
            self._store.subscribe()

        self._orchestrator = Orchestrator(self.config, self._adapter, router, supervisor)

    async def run(self, goal: str, target: str) -> ResultObject:
        task = self._adapter.normalize(goal, target)
        result = await self._orchestrator.run(task)
        self._mcp.shutdown()
        if self._store is not None:
            score, label = risk_score(result.artifacts)
            self._store.record_run(
                RunRecord(
                    task_id=result.task_id,
                    client=result.source_client,
                    goal=goal,
                    target=target,
                    status=result.status,
                    risk_label=label,
                    risk_score=score,
                    tokens_used=result.tokens_used,
                    tokens_budget=result.tokens_budget,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                )
            )
        return result
