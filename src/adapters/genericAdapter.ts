/**
 * Generic client adapter.
 *
 * Implements the ClientAdapter contract for any client. It normalizes a goal
 * into a TaskObject and, for offline operation, builds a HeuristicWorker. A
 * concrete adapter (Claude API, Gemini CLI, MCP-based Cursor/Duo, etc.) would
 * subclass this and override createWorker() to call the real model, plus
 * formatResult() to match the client's native response shape.
 */

import { uuid, shortId } from '../util/ids.js';
import { HeuristicWorker } from './heuristicWorker.js';
import type { ClientAdapter, WorkerAgent } from './types.js';
import type { Phase, ResultObject, SourceClient, TaskObject } from '../core/types.js';

function parseTarget(raw: string): { host: string; ports?: number[]; paths?: string[] } {
  // Accept "host", "host:port", or a URL.
  let host = raw.trim();
  try {
    if (/^https?:\/\//.test(host)) host = new URL(host).hostname;
  } catch {
    /* keep raw */
  }
  const [h, port] = host.split(':');
  const ports = port ? [parseInt(port, 10)].filter((n) => !Number.isNaN(n)) : undefined;
  return { host: h, ports };
}

function inferRequestType(input: string): Phase {
  const t = input.toLowerCase();
  if (/reverse|binary|\bexe\b|ghidra|decompile/.test(t)) return 'analysis';
  if (/exploit|shell|access/.test(t)) return 'exploit';
  if (/enumerat/.test(t)) return 'enumeration';
  if (/scan|vulnerab|secure|owasp/.test(t)) return 'vuln_scan';
  return 'recon';
}

export class GenericAdapter implements ClientAdapter {
  constructor(
    public readonly id: SourceClient,
    private readonly simulateLoopOn?: string,
  ) {}

  normalize(input: string, target: string, overrides: Partial<TaskObject> = {}): TaskObject {
    const tgt = parseTarget(target);
    const base: TaskObject = {
      taskId: uuid(),
      sourceClient: this.id,
      requestType: inferRequestType(input),
      naturalInput: input,
      target: tgt,
      context: { sessionId: shortId('sess'), priorFindings: [], activePhase: 'recon' },
      constraints: {
        scopeId: 'default',
        maxTokens: 200_000,
        riskLevel: 'medium',
        timeoutMs: 600_000,
      },
    };
    return { ...base, ...overrides, constraints: { ...base.constraints, ...overrides.constraints } };
  }

  createWorker(task: TaskObject): WorkerAgent {
    return new HeuristicWorker({ target: task.target, simulateLoopOn: this.simulateLoopOn });
  }

  formatResult(result: ResultObject): unknown {
    // Generic shape; client-specific adapters reshape this for their protocol.
    return {
      task_id: result.taskId,
      client: result.sourceClient,
      status: result.status,
      summary: result.summary,
      findings: result.artifacts.map((a) => ({ type: a.kind, value: a.value, detail: a.detail })),
      phases_completed: result.phasesCompleted,
      tokens: { used: result.tokensUsed, budget: result.tokensBudget },
      duration_ms: result.finishedAt - result.startedAt,
    };
  }
}
