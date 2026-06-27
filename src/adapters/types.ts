/**
 * Layer 1 — AI Client Adapter contract.
 *
 * Each supported AI client implements this interface. Internally everything
 * speaks TaskObject / ResultObject; the adapter is the only place that knows a
 * client's native protocol (REST, JSON-RPC, MCP, VS Code API, etc.).
 *
 * The `WorkerAgent` abstraction represents the actual AI doing the work: given
 * the current findings, it decides the next tool call (or signals done). In
 * production this is the live Claude/Gemini/etc. call; for offline runs a
 * heuristic stand-in implements the same interface.
 */

import type { Artifact, Phase, ResultObject, TaskObject, ToolCall, ToolResult } from '../core/types.js';

export interface AdapterContext {
  phase: Phase;
  toolWhitelist: string[];
  /** All findings discovered so far this session. */
  findings: Artifact[];
  /** Supervisor feedback to consider before the next decision, if any. */
  feedback?: string;
}

/** A single decision from the worker AI. */
export type AgentDecision =
  | { type: 'tool_call'; call: Omit<ToolCall, 'callId' | 'agentId' | 'taskId'> }
  | { type: 'done'; reason: string };

export interface WorkerAgent {
  /** Decide the next action given current context. */
  next(ctx: AdapterContext): Promise<AgentDecision>;
  /** Receive a tool result so the agent can update its reasoning. */
  observe(result: ToolResult): void;
}

export interface ClientAdapter {
  readonly id: string;
  /** Normalize a raw natural-language goal into a TaskObject. */
  normalize(input: string, target: string, overrides?: Partial<TaskObject>): TaskObject;
  /** Construct the worker agent that will drive this session. */
  createWorker(task: TaskObject): WorkerAgent;
  /** Translate the final internal result back to the client's native shape. */
  formatResult(result: ResultObject): unknown;
}
