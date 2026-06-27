"""The Orchestrator — wires the layers + the supervisor into one run.

Lifecycle of a request:
  1. L1 adapter normalizes the goal into a TaskObject.
  2. L5 decomposer plans phases with per-phase budgets + whitelists.
  3. For each phase, a worker agent loops: decide -> supervisor.before_call ->
     L2 router dispatch (L3/L4) -> supervisor.after_result -> apply intervention.
  4. The supervisor steers (redirect / wrap_up / advance_phase / escalate)
     without ever executing a tool itself.
  5. A final report aggregates all findings and returns via the adapter.
"""

from __future__ import annotations

import time

from ..adapters.base import ClientAdapter, DoneDecision, ToolCallDecision
from ..router.router import TaskRouter
from ..supervisor.decomposer import PlanNode, TaskDecomposer
from ..supervisor.supervisor import Supervisor
from ..util.ids import estimate_tokens, short_id, uuid
from ..util.logger import get_logger
from .config import SentinelConfig
from .events import bus
from .reporter import build_summary
from .types import Phase, ResultObject, TaskObject, ToolCall

_log = get_logger("orchestrator")

# Safety valve: max worker decisions per phase regardless of supervisor.
_MAX_CALLS_PER_PHASE = 30


class Orchestrator:
    def __init__(
        self,
        config: SentinelConfig,
        adapter: ClientAdapter,
        router: TaskRouter,
        supervisor: Supervisor,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._router = router
        self._supervisor = supervisor
        self._decomposer = TaskDecomposer(config)

    async def run(self, task: TaskObject) -> ResultObject:
        started_at = int(time.time() * 1000)
        agent_id = short_id("agent")
        worker = self._adapter.create_worker(task)
        plan = self._decomposer.plan(task)
        _log.info("planned %d phases: %s", len(plan), " → ".join(p.phase for p in plan))

        phases_completed: list[Phase] = []
        aborted = False

        for i, node in enumerate(plan):
            if i == 0:
                self._supervisor.register(agent_id, task.task_id, node.phase, node.token_budget)
            else:
                self._supervisor.set_phase(agent_id, node.phase, node.token_budget)

            surface_before = len(self._supervisor.all_artifacts(agent_id))
            outcome = await self._run_phase(agent_id, task, node, worker)
            phases_completed.append(node.phase)

            if outcome == "abort":
                aborted = True
                break

            surface_after = len(self._supervisor.all_artifacts(agent_id))
            if surface_before > 0:
                self._decomposer.reallocate(plan, i, surface_after / surface_before)

        artifacts = self._supervisor.all_artifacts(agent_id)
        tokens_used = self._supervisor.tokens_used(agent_id) + estimate_tokens(str(artifacts))
        result = ResultObject(
            task_id=task.task_id,
            source_client=task.source_client,
            status="aborted" if aborted else "complete",
            summary=build_summary(artifacts, phases_completed),
            artifacts=artifacts,
            phases_completed=phases_completed,
            tokens_used=tokens_used,
            tokens_budget=task.constraints.max_tokens,
            started_at=started_at,
            finished_at=int(time.time() * 1000),
        )
        bus.emit("task:complete", {"taskId": task.task_id})
        return result

    async def _run_phase(self, agent_id: str, task: TaskObject, node: PlanNode, worker) -> str:
        feedback: str | None = None

        for _ in range(_MAX_CALLS_PER_PHASE):
            findings = self._supervisor.all_artifacts(agent_id)
            from ..adapters.base import AdapterContext

            decision = await worker.next(
                AdapterContext(phase=node.phase, tool_whitelist=node.tool_whitelist, findings=findings, feedback=feedback)
            )
            feedback = None

            if isinstance(decision, DoneDecision):
                _log.debug("worker finished phase '%s': %s", node.phase, decision.reason)
                return "done"

            assert isinstance(decision, ToolCallDecision)

            if node.tool_whitelist and decision.tool.lower() not in node.tool_whitelist:
                feedback = (
                    f"[SUPERVISOR:WHITELIST] Tool '{decision.tool}' is not permitted in the '{node.phase}' phase. "
                    f"Allowed: {', '.join(node.tool_whitelist)}."
                )
                continue

            call = ToolCall(
                call_id=uuid(),
                agent_id=agent_id,
                task_id=task.task_id,
                phase=decision.phase,
                tool=decision.tool,
                params=decision.params,
                description=decision.description,
            )

            pre = self._supervisor.before_call(agent_id, call)
            if pre and pre.kind == "escalate":
                gate = await self._supervisor.request_human_gate(
                    agent_id, "LOOP_ESCALATION", pre.feedback or "sub-agent looping; auto-correction failed"
                )
                if gate == "deny":
                    return "abort"
                feedback = pre.feedback
                continue
            if pre and pre.kind == "redirect":
                feedback = pre.feedback
                continue

            if node.requires_human_gate:
                gate = await self._supervisor.request_human_gate(
                    agent_id, "HIGH_RISK", f"Tool: {call.tool}, Target: {task.target.host}, Action: {call.description or 'n/a'}"
                )
                if gate == "deny":
                    feedback = (
                        f"[SUPERVISOR:HIGH_RISK] Human denied execution of '{call.tool}'. "
                        f"Choose a non-destructive alternative or finish the phase."
                    )
                    continue

            result = await self._router.dispatch(call, task.target)
            worker.observe(result)

            post = self._supervisor.after_result(agent_id, result)
            if post.kind == "advance_phase":
                return "done"
            if post.kind == "wrap_up":
                feedback = post.feedback
                await worker.next(
                    AdapterContext(phase=node.phase, tool_whitelist=node.tool_whitelist, findings=findings, feedback=feedback)
                )
                return "done"
            if post.kind == "redirect":
                feedback = post.feedback

        _log.warning("phase '%s' hit MAX_CALLS_PER_PHASE safety valve", node.phase)
        return "done"
