/**
 * Loop Detector (Supervisor sub-component 8.2.3).
 *
 * Runs after every tool call. Computes a fuzzy signature of each
 * (tool, target, key-params) tuple and fires LOOP_DETECTED when K consecutive
 * recent calls are near-identical. Recon tools get a higher tolerance because
 * scanning is inherently iterative; exploit-class tools fire sooner.
 *
 * Output is an ACTIONABLE redirect, not just "stop".
 */

import type { ToolCall } from '../core/types.js';
import type { SubAgentState } from './state.js';

export interface LoopVerdict {
  looping: boolean;
  repeatedCount: number;
  signature: string;
  message?: string;
}

const RECON_TOOLS = new Set(['nmap', 'subfinder', 'amass', 'shodan', 'theharvester']);

/** Normalized signature for fuzzy comparison of two calls. */
function signature(call: ToolCall): string {
  const tool = call.tool.toLowerCase();
  const host = String(call.params.host ?? call.params.target ?? '');
  const ports = String(call.params.ports ?? '');
  const path = String(call.params.path ?? call.params.url ?? '');
  return `${tool}|${host}|${ports}|${path}`;
}

export class LoopDetector {
  constructor(private readonly baseThreshold: number) {}

  check(state: SubAgentState, latest: ToolCall): LoopVerdict {
    const sig = signature(latest);
    const tool = latest.tool.toLowerCase();
    const threshold = RECON_TOOLS.has(tool) ? this.baseThreshold + 2 : this.baseThreshold;

    // Count trailing consecutive calls sharing this signature.
    let repeated = 0;
    for (let i = state.toolCallLog.length - 1; i >= 0; i--) {
      if (signature(state.toolCallLog[i]) === sig) repeated++;
      else break;
    }

    if (repeated >= threshold) {
      const newFindings = state.callsSinceLastArtifact === 0 ? 'some' : '0';
      const msg =
        `You have called '${tool}' on '${latest.params.host ?? latest.params.target}' ${repeated} times ` +
        `with near-identical parameters and found ${newFindings} new findings in the last calls. ` +
        `The information you need is not there. ${this.suggestAlternative(state)}`;
      return { looping: true, repeatedCount: repeated, signature: sig, message: msg };
    }
    return { looping: false, repeatedCount: repeated, signature: sig };
  }

  /** Phase-aware actionable suggestion for the next step. */
  private suggestAlternative(state: SubAgentState): string {
    const openPorts = state.artifacts.filter((a) => a.kind === 'port').map((a) => a.value);
    switch (state.currentPhase) {
      case 'recon':
        return openPorts.length
          ? `Move to enumeration: enumerate the open ports already found (${openPorts.join(', ')}).`
          : `Switch discovery technique or target a different host/range instead of repeating this scan.`;
      case 'enumeration':
        return `Pivot to vulnerability scanning against the services you have already enumerated.`;
      case 'vuln_scan':
        return `Stop re-scanning. Triage the findings you have and decide whether any warrant exploitation.`;
      default:
        return `Advance to the next phase using the findings already collected.`;
    }
  }
}
