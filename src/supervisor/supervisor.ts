/**
 * Layer 5 — AI Supervisor Engine (the core differentiator).
 *
 * Cross-cutting meta-layer that observes every sub-agent in real time and
 * steers it WITHOUT executing tools itself. After each tool result it runs:
 *   - artifact merge + progress scoring
 *   - loop detection
 *   - token budget evaluation
 * and, when a failure mode is detected, formats an ACTIONABLE corrective
 * feedback message and routes it through the agent's native channel. It also
 * manages human escalation gates.
 *
 * The supervisor returns an Intervention describing what the worker should do;
 * the orchestrator applies it.
 */

import { bus } from '../core/events.js';
import { LoopDetector } from './loopDetector.js';
import { ProgressScorer } from './progressScorer.js';
import { TokenBudgetManager } from './tokenBudget.js';
import { FeedbackInjector } from './feedbackInjector.js';
import { EscalationManager, type HumanGate } from './escalation.js';
import {
  createState,
  recordCall,
  mergeArtifacts,
  type SubAgentState,
} from './state.js';
import type { VexqrConfig } from '../core/config.js';
import type { Artifact, Phase, SourceClient, ToolCall, ToolResult } from '../core/types.js';

export type InterventionKind = 'continue' | 'redirect' | 'wrap_up' | 'stop' | 'advance_phase' | 'escalate';

export interface Intervention {
  kind: InterventionKind;
  /** Feedback payload to hand back to the worker AI, if any. */
  feedback?: string;
  reason?: string;
  novelArtifacts: Artifact[];
}

export class Supervisor {
  private readonly states = new Map<string, SubAgentState>();
  private readonly loop: LoopDetector;
  private readonly progress: ProgressScorer;
  private readonly budget: TokenBudgetManager;
  private readonly injector = new FeedbackInjector();
  private readonly escalation: EscalationManager;

  constructor(
    private readonly config: VexqrConfig,
    private readonly client: SourceClient,
    humanGate: HumanGate,
  ) {
    this.loop = new LoopDetector(config.supervisor.loopThreshold);
    this.progress = new ProgressScorer(config.supervisor.productivityWindow);
    this.budget = new TokenBudgetManager(config.supervisor.tokenSafetyMargin);
    this.escalation = new EscalationManager(humanGate);
  }

  register(agentId: string, taskId: string, phase: Phase, tokenBudget: number): void {
    this.states.set(agentId, createState(agentId, taskId, phase, tokenBudget));
    bus.emit('phase:enter', { taskId, phase });
  }

  setPhase(agentId: string, phase: Phase, tokenBudget: number): void {
    const s = this.states.get(agentId);
    if (!s) return;
    s.currentPhase = phase;
    s.tokensBudget = tokenBudget;
    s.tokensUsed = 0;
    s.callsSinceLastArtifact = 0;
    s.loopFireCount = 0;
    s.status = 'active';
    bus.emit('phase:enter', { taskId: s.taskId, phase });
  }

  /** Called BEFORE a tool runs: records the call + checks for loops. */
  beforeCall(agentId: string, call: ToolCall): Intervention | null {
    const state = this.states.get(agentId);
    if (!state) return null;
    recordCall(state, call);

    const verdict = this.loop.check(state, call);
    if (verdict.looping) {
      state.loopFireCount += 1;
      state.status = 'looping';

      if (state.loopFireCount >= this.config.supervisor.loopEscalationLimit) {
        return { kind: 'escalate', reason: 'LOOP_ESCALATION', feedback: verdict.message, novelArtifacts: [] };
      }
      const fb = this.injector.inject(this.client, {
        agentId,
        reason: 'LOOP_DETECTED',
        message: verdict.message!,
      });
      return { kind: 'redirect', feedback: fb.payload, reason: 'LOOP_DETECTED', novelArtifacts: [] };
    }
    return null;
  }

  /** Called AFTER a tool runs: merges artifacts, scores progress, checks budget. */
  afterResult(agentId: string, result: ToolResult): Intervention {
    const state = this.states.get(agentId);
    if (!state) return { kind: 'continue', novelArtifacts: [] };

    const novel = mergeArtifacts(state, result.artifacts);
    for (const a of novel) bus.emit('artifact:new', { taskId: state.taskId, agentId, artifact: a });

    // 1. Token budget takes precedence — it can force a wrap-up.
    const b = this.budget.consume(state, result.tokenCost);
    bus.emit('budget:level', { agentId, level: b.level, tokensUsed: state.tokensUsed, tokensBudget: state.tokensBudget });
    if (b.stop) {
      state.status = 'budget_warning';
      const fb = this.injector.inject(this.client, { agentId, reason: b.level.toUpperCase(), message: b.message! });
      return { kind: 'wrap_up', feedback: fb.payload, reason: b.level, novelArtifacts: novel };
    }
    if (b.message) {
      this.injector.inject(this.client, { agentId, reason: b.level.toUpperCase(), message: b.message });
    }

    // 2. Progress scoring — phase completion or low-productivity pivot.
    const p = this.progress.check(state);
    if (p.phaseComplete) {
      bus.emit('phase:complete', { taskId: state.taskId, phase: state.currentPhase });
      return { kind: 'advance_phase', feedback: p.message, reason: 'PHASE_COMPLETE', novelArtifacts: novel };
    }
    if (!p.productive && p.message) {
      const fb = this.injector.inject(this.client, { agentId, reason: 'LOW_PRODUCTIVITY', message: p.message });
      return { kind: 'redirect', feedback: fb.payload, reason: 'LOW_PRODUCTIVITY', novelArtifacts: novel };
    }

    state.status = 'active';
    return { kind: 'continue', novelArtifacts: novel };
  }

  /** Route a high-risk / scope / contradiction decision to a human. */
  async requestHumanGate(
    agentId: string,
    reason: 'HIGH_RISK' | 'SCOPE_BOUNDARY' | 'CRITICAL_FINDING' | 'PLAN_CONTRADICTION' | 'LOOP_ESCALATION',
    summary: string,
    options: string[] = ['approve', 'deny'],
  ): Promise<'approve' | 'deny'> {
    const s = this.states.get(agentId);
    if (s) s.status = 'escalated';
    return this.escalation.escalate({ agentId, reason, summary, options });
  }

  state(agentId: string): SubAgentState | undefined {
    return this.states.get(agentId);
  }

  allArtifacts(agentId: string): Artifact[] {
    return this.states.get(agentId)?.artifacts ?? [];
  }

  tokensUsed(agentId: string): number {
    return this.states.get(agentId)?.tokensUsed ?? 0;
  }
}
