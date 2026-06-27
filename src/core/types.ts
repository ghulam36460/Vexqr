/**
 * Core domain types for the Aegix orchestration platform.
 *
 * These are the internal "lingua franca" of the whole system. Every AI client
 * adapter (L1) normalizes its native protocol into a TaskObject, and every
 * layer below operates on these shared shapes. This is what lets us add a new
 * AI client by writing a single adapter, with zero changes elsewhere.
 */

/** Supported AI client identifiers. */
export type SourceClient =
  | 'claude_api'
  | 'claude_code'
  | 'gemini_cli'
  | 'copilot'
  | 'gitlab_duo'
  | 'cursor'
  | 'codex'
  | 'custom';

/** Security operation phases, executed in dependency order. */
export const PHASES = [
  'recon',
  'enumeration',
  'vuln_scan',
  'exploit',
  'analysis',
  'post_exploit',
  'report',
] as const;

export type Phase = (typeof PHASES)[number];

/** A security target the operation is scoped to. */
export interface Target {
  host: string;
  ports?: number[];
  paths?: string[];
}

/** Constraints applied to a task by scope, budget and risk policy. */
export interface TaskConstraints {
  scopeId: string;
  maxTokens: number;
  /** 'low' tasks auto-run; 'high' tasks require a human confirmation gate. */
  riskLevel: 'low' | 'medium' | 'high';
  timeoutMs: number;
}

/** Conversational / session context carried between calls. */
export interface TaskContext {
  sessionId: string;
  priorFindings: Artifact[];
  activePhase: Phase;
}

/**
 * The unified internal task representation. Produced by L1 adapters,
 * consumed by everything downstream.
 */
export interface TaskObject {
  taskId: string;
  sourceClient: SourceClient;
  requestType: Phase;
  naturalInput: string;
  target: Target;
  toolsHint?: string[];
  context: TaskContext;
  constraints: TaskConstraints;
}

/** A single atomic, novel piece of intelligence discovered during a run. */
export interface Artifact {
  /** Stable category used for dedup + progress scoring. */
  kind: 'host' | 'port' | 'service' | 'cve' | 'path' | 'credential' | 'domain' | 'finding';
  value: string;
  /** Optional source tool + free-form detail. */
  source?: string;
  detail?: string;
  discoveredAt: number;
}

/** How a tool will be / was executed. */
export type RouteKind = 'mcp' | 'terminal' | 'internal';

/** A request from a sub-agent to run a single tool. */
export interface ToolCall {
  callId: string;
  agentId: string;
  taskId: string;
  phase: Phase;
  tool: string;
  params: Record<string, unknown>;
  /** Free text describing the action, used for risk classification + audit. */
  description?: string;
}

/** Normalized result of a tool execution, regardless of route. */
export interface ToolResult {
  callId: string;
  tool: string;
  route: RouteKind;
  status: 'ok' | 'error' | 'timeout' | 'blocked';
  /** Structured findings extracted by the output parser. */
  artifacts: Artifact[];
  /** Raw or summarized human-readable output. */
  output: string;
  errors: string[];
  /** Tokens the result is estimated to cost when fed back to the agent. */
  tokenCost: number;
  durationMs: number;
  /** True when the result is a corrective message injected by the supervisor. */
  isSupervisorFeedback?: boolean;
}

/** Final object returned to the originating AI client. */
export interface ResultObject {
  taskId: string;
  sourceClient: SourceClient;
  status: 'complete' | 'partial' | 'aborted';
  summary: string;
  artifacts: Artifact[];
  phasesCompleted: Phase[];
  tokensUsed: number;
  tokensBudget: number;
  startedAt: number;
  finishedAt: number;
}
