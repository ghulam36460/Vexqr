/**
 * Progress Scorer (Supervisor sub-component 8.2.4).
 *
 * Measures whether the sub-agent is producing new actionable findings or just
 * making noise. Fires LOW_PRODUCTIVITY after a window of calls with no novel
 * artifacts, and detects phase completion (diminishing returns) so the
 * decomposer can advance to the next phase.
 */

import type { SubAgentState } from './state.js';

export interface ProgressVerdict {
  productive: boolean;
  phaseComplete: boolean;
  message?: string;
}

export class ProgressScorer {
  constructor(private readonly window: number) {}

  check(state: SubAgentState): ProgressVerdict {
    const stale = state.callsSinceLastArtifact;

    // Diminishing returns => phase complete.
    if (stale >= this.window && state.artifacts.length > 0) {
      return {
        productive: false,
        phaseComplete: true,
        message:
          `Phase '${state.currentPhase}' has reached diminishing returns ` +
          `(${stale} calls without a new finding, ${state.artifacts.length} artifacts collected). ` +
          `Advancing to the next phase.`,
      };
    }

    // Low productivity, but not yet complete => pivot injection.
    if (stale >= this.window) {
      return {
        productive: false,
        phaseComplete: false,
        message:
          `This chain has not generated new findings in the last ${stale} calls. ` +
          `Current known attack surface: ${this.surfaceSummary(state)}. ` +
          `Recommended next step: try a different technique or target rather than continuing this approach.`,
      };
    }

    return { productive: true, phaseComplete: false };
  }

  private surfaceSummary(state: SubAgentState): string {
    const counts = new Map<string, number>();
    for (const a of state.artifacts) counts.set(a.kind, (counts.get(a.kind) ?? 0) + 1);
    if (counts.size === 0) return 'none yet';
    return [...counts.entries()].map(([k, n]) => `${n} ${k}${n > 1 ? 's' : ''}`).join(', ');
  }
}
