/**
 * Heuristic worker agent.
 *
 * A deterministic stand-in for a live AI client used for offline runs, demos
 * and tests. It deliberately exhibits the failure modes the Supervisor exists
 * to catch (repeating a scan, low-productivity tangents) so the supervision
 * loop is observable end-to-end. A real adapter swaps this for live model calls
 * behind the same WorkerAgent interface.
 */

import type { AdapterContext, AgentDecision, WorkerAgent } from './types.js';
import type { Target, ToolResult } from '../core/types.js';

export interface HeuristicOptions {
  target: Target;
  /** Inject a loop on this tool to demonstrate loop detection. */
  simulateLoopOn?: string;
}

/** First-choice tool per phase. */
const PHASE_PRIMARY: Record<string, string> = {
  recon: 'nmap',
  enumeration: 'gobuster',
  vuln_scan: 'nuclei',
  exploit: 'metasploit',
  analysis: 'ghidra',
  post_exploit: 'volatility',
  report: '',
};

export class HeuristicWorker implements WorkerAgent {
  private callsThisPhase = 0;
  private lastPhase = '';
  private redirected = false;

  constructor(private readonly opts: HeuristicOptions) {}

  async next(ctx: AdapterContext): Promise<AgentDecision> {
    if (ctx.phase !== this.lastPhase) {
      this.callsThisPhase = 0;
      this.redirected = false;
      this.lastPhase = ctx.phase;
    }

    // Respect supervisor feedback: a redirect makes the worker change course.
    if (ctx.feedback && /LOOP_DETECTED|LOW_PRODUCTIVITY/.test(ctx.feedback)) {
      this.redirected = true;
    }

    const primary = PHASE_PRIMARY[ctx.phase] ?? '';
    if (!primary || ctx.phase === 'report') {
      return { type: 'done', reason: `phase '${ctx.phase}' produces a report, no tools to call` };
    }

    this.callsThisPhase += 1;

    // Demonstrate a loop: keep calling the same tool until the supervisor
    // redirects, then stop.
    if (this.opts.simulateLoopOn === primary && !this.redirected && this.callsThisPhase <= 6) {
      return {
        type: 'tool_call',
        call: {
          phase: ctx.phase,
          tool: primary,
          params: { host: this.opts.target.host },
          description: `${ctx.phase} scan with ${primary}`,
        },
      };
    }

    // Normal flow: run the phase's primary tool a couple of times, then finish.
    if (this.callsThisPhase <= 2 && !this.redirected) {
      return {
        type: 'tool_call',
        call: {
          phase: ctx.phase,
          tool: primary,
          params: { host: this.opts.target.host },
          description: `${ctx.phase} scan with ${primary}`,
        },
      };
    }

    return { type: 'done', reason: `phase '${ctx.phase}' complete` };
  }

  observe(_result: ToolResult): void {
    /* a live agent would update its reasoning here */
  }
}
