/**
 * The Orchestrator — wires the layers + the supervisor into one run.
 *
 * Lifecycle of a request:
 *   1. L1 adapter normalizes the goal into a TaskObject.
 *   2. L5 decomposer plans phases (DAG) with per-phase budgets + whitelists.
 *   3. For each phase, a worker agent loops: decide → supervisor.beforeCall →
 *      L2 router dispatch (L3/L4) → supervisor.afterResult → apply intervention.
 *   4. The supervisor steers (redirect / wrap_up / advance_phase / escalate)
 *      without ever executing a tool itself.
 *   5. A final report aggregates all findings and returns via the adapter.
 */

import { createLogger } from '../util/logger.js';
import { bus } from '../core/events.js';
import { shortId, uuid, estimateTokens } from '../util/ids.js';
import { buildSummary } from './reporter.js';
import { TaskDecomposer, type PlanNode } from '../supervisor/decomposer.js';
import { Supervisor } from '../supervisor/supervisor.js';
import { TaskRouter } from '../router/router.js';
import type { ClientAdapter } from '../adapters/types.js';
import type { SentinelConfig } from './config.js';
import type { Phase, ResultObject, TaskObject, ToolCall } from './types.js';

const log = createLogger('orchestrator');

/** Safety valve: max worker decisions per phase regardless of supervisor. */
const MAX_CALLS_PER_PHASE = 30;

export interface OrchestratorDeps {
  config: SentinelConfig;
  adapter: ClientAdapter;
  router: TaskRouter;
  supervisor: Supervisor;
}

export class Orchestrator {
  private readonly decomposer: TaskDecomposer;

  constructor(private readonly deps: OrchestratorDeps) {
    this.decomposer = new TaskDecomposer(deps.config);
  }

  async run(task: TaskObject): Promise<ResultObject> {
    const startedAt = Date.now();
    const agentId = shortId('agent');
    const worker = this.deps.adapter.createWorker(task);
    const plan = this.decomposer.plan(task);

    log.info(`planned ${plan.length} phases: ${plan.map((p) => p.phase).join(' → ')}`);

    const phasesCompleted: Phase[] = [];
    let aborted = false;

    for (let i = 0; i < plan.length; i++) {
      const node = plan[i];

      if (i === 0) this.deps.supervisor.register(agentId, task.taskId, node.phase, node.tokenBudget);
      else this.deps.supervisor.setPhase(agentId, node.phase, node.tokenBudget);

      const surfaceBefore = this.deps.supervisor.allArtifacts(agentId).length;
      const outcome = await this.runPhase(agentId, task, node, worker);
      phasesCompleted.push(node.phase);

      if (outcome === 'abort') {
        aborted = true;
        break;
      }

      // Re-planning: if recon exploded the surface, grow later phase budgets.
      const surfaceAfter = this.deps.supervisor.allArtifacts(agentId).length;
      if (surfaceBefore > 0) {
        this.decomposer.reallocate(plan, i, surfaceAfter / surfaceBefore);
      }
    }

    const artifacts = this.deps.supervisor.allArtifacts(agentId);
    const tokensUsed = this.deps.supervisor.tokensUsed(agentId) + estimateTokens(JSON.stringify(artifacts));
    const result: ResultObject = {
      taskId: task.taskId,
      sourceClient: task.sourceClient,
      status: aborted ? 'aborted' : 'complete',
      summary: buildSummary(artifacts, phasesCompleted),
      artifacts,
      phasesCompleted,
      tokensUsed,
      tokensBudget: task.constraints.maxTokens,
      startedAt,
      finishedAt: Date.now(),
    };
    bus.emit('task:complete', { taskId: task.taskId });
    return result;
  }

  /** Run a single phase to completion (or until supervisor advances/aborts). */
  private async runPhase(
    agentId: string,
    task: TaskObject,
    node: PlanNode,
    worker: ReturnType<ClientAdapter['createWorker']>,
  ): Promise<'done' | 'abort'> {
    let feedback: string | undefined;

    for (let n = 0; n < MAX_CALLS_PER_PHASE; n++) {
      const findings = this.deps.supervisor.allArtifacts(agentId);
      const decision = await worker.next({
        phase: node.phase,
        toolWhitelist: node.toolWhitelist,
        findings,
        feedback,
      });
      feedback = undefined;

      if (decision.type === 'done') {
        log.debug(`worker finished phase '${node.phase}': ${decision.reason}`);
        return 'done';
      }

      // Whitelist enforcement: a phase agent can only use its allowed tools.
      if (node.toolWhitelist.length && !node.toolWhitelist.includes(decision.call.tool.toLowerCase())) {
        feedback = `[SUPERVISOR:WHITELIST] Tool '${decision.call.tool}' is not permitted in the '${node.phase}' phase. Allowed: ${node.toolWhitelist.join(', ')}.`;
        continue;
      }

      const call: ToolCall = {
        callId: uuid(),
        agentId,
        taskId: task.taskId,
        ...decision.call,
      };

      // Supervisor pre-check (loop detection).
      const pre = this.deps.supervisor.beforeCall(agentId, call);
      if (pre?.kind === 'escalate') {
        const decisionGate = await this.deps.supervisor.requestHumanGate(
          agentId,
          'LOOP_ESCALATION',
          pre.feedback ?? 'sub-agent looping; auto-correction failed',
        );
        if (decisionGate === 'deny') return 'abort';
        feedback = pre.feedback;
        continue;
      }
      if (pre?.kind === 'redirect') {
        feedback = pre.feedback;
        continue; // do not execute the looping call; let the worker re-decide
      }

      // Human gate for high-risk phases (e.g. exploit).
      if (node.requiresHumanGate) {
        const gate = await this.deps.supervisor.requestHumanGate(
          agentId,
          'HIGH_RISK',
          `Tool: ${call.tool}, Target: ${task.target.host}, Action: ${call.description ?? 'n/a'}`,
        );
        if (gate === 'deny') {
          feedback = `[SUPERVISOR:HIGH_RISK] Human denied execution of '${call.tool}'. Choose a non-destructive alternative or finish the phase.`;
          continue;
        }
      }

      // Dispatch through L2 → L3/L4.
      const result = await this.deps.router.dispatch(call, task.target);
      worker.observe(result);

      // Supervisor post-check (progress, budget).
      const post = this.deps.supervisor.afterResult(agentId, result);
      if (post.kind === 'advance_phase') return 'done';
      if (post.kind === 'wrap_up') {
        feedback = post.feedback;
        // Allow the worker one wrap-up turn, then end the phase.
        await worker.next({ phase: node.phase, toolWhitelist: node.toolWhitelist, findings, feedback });
        return 'done';
      }
      if (post.kind === 'redirect') feedback = post.feedback;
    }

    log.warn(`phase '${node.phase}' hit MAX_CALLS_PER_PHASE safety valve`);
    return 'done';
  }
}
