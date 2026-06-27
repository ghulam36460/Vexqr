"""Generic client adapter.

Implements the ClientAdapter contract for any client. It normalizes a goal into
a TaskObject and, for offline operation, builds a HeuristicWorker. A concrete
adapter (Claude API, Gemini CLI, MCP-based Cursor/Duo, etc.) would subclass this
and override ``create_worker`` to call the real model, plus ``format_result`` to
match the client's native response shape.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..core.types import Phase, ResultObject, SourceClient, TaskConstraints, TaskContext, TaskObject, Target
from ..util.ids import short_id, uuid
from .base import WorkerAgent
from .heuristic_worker import HeuristicWorker


def _parse_target(raw: str) -> Target:
    host = raw.strip()
    if re.match(r"^https?://", host):
        parsed = urlparse(host)
        host = parsed.hostname or host
    h, _, port = host.partition(":")
    ports = [int(port)] if port.isdigit() else None
    return Target(host=h, ports=ports)


def _infer_request_type(text: str) -> Phase:
    t = text.lower()
    if re.search(r"reverse|binary|\bexe\b|ghidra|decompile", t):
        return "analysis"
    if re.search(r"exploit|shell|access", t):
        return "exploit"
    if re.search(r"enumerat", t):
        return "enumeration"
    if re.search(r"scan|vulnerab|secure|owasp", t):
        return "vuln_scan"
    return "recon"


class GenericAdapter:
    def __init__(self, client: SourceClient, simulate_loop_on: str | None = None) -> None:
        self.id = client
        self._client = client
        self._simulate_loop_on = simulate_loop_on

    def normalize(self, input_text: str, target: str, overrides: dict[str, Any] | None = None) -> TaskObject:
        overrides = overrides or {}
        return TaskObject(
            task_id=uuid(),
            source_client=self._client,
            request_type=overrides.get("request_type", _infer_request_type(input_text)),
            natural_input=input_text,
            target=_parse_target(target),
            context=TaskContext(session_id=short_id("sess")),
            constraints=overrides.get("constraints", TaskConstraints()),
        )

    def create_worker(self, task: TaskObject) -> WorkerAgent:
        return HeuristicWorker(task.target, self._simulate_loop_on)

    def format_result(self, result: ResultObject) -> Any:
        return result.to_native()
