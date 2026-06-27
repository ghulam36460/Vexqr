/**
 * Per-sub-agent state tracked by the Supervisor monitor.
 *
 * Updated on every tool call/result. The loop detector, progress scorer and
 * budget manager all read from this object.
 */

import type { Artifact, Phase, ToolCall } from '../core/types.js';

export type AgentStatus = 'active' | 'stalled' | 'looping' | 'budget_warning' | 'escalated' | 'complete';

export interface SubAgentState {
  agentId: string;
  taskId: string;
  currentPhase: Phase;
  /** Sliding window of recent calls (last 20). */
  toolCallLog: ToolCall[];
  /** All novel artifacts found this session (deduped). */
  artifacts: Artifact[];
  tokensUsed: number;
  tokensBudget: number;
  loopFireCount: number;
  callsSinceLastArtifact: number;
  lastNewArtifactAt: number;
  status: AgentStatus;
}

const WINDOW = 20;

export function createState(agentId: string, taskId: string, phase: Phase, budget: number): SubAgentState {
  return {
    agentId,
    taskId,
    currentPhase: phase,
    toolCallLog: [],
    artifacts: [],
    tokensUsed: 0,
    tokensBudget: budget,
    loopFireCount: 0,
    callsSinceLastArtifact: 0,
    lastNewArtifactAt: Date.now(),
    status: 'active',
  };
}

export function recordCall(state: SubAgentState, call: ToolCall): void {
  state.toolCallLog.push(call);
  if (state.toolCallLog.length > WINDOW) state.toolCallLog.shift();
}

/** Merge new artifacts, returning only the ones that were genuinely novel. */
export function mergeArtifacts(state: SubAgentState, incoming: Artifact[]): Artifact[] {
  const seen = new Set(state.artifacts.map((a) => `${a.kind}:${a.value}`));
  const novel: Artifact[] = [];
  for (const a of incoming) {
    const key = `${a.kind}:${a.value}`;
    if (!seen.has(key)) {
      seen.add(key);
      novel.push(a);
      state.artifacts.push(a);
    }
  }
  if (novel.length > 0) {
    state.callsSinceLastArtifact = 0;
    state.lastNewArtifactAt = Date.now();
  } else {
    state.callsSinceLastArtifact += 1;
  }
  return novel;
}
