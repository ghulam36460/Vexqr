/**
 * Token Budget Manager (Supervisor sub-component 8.2.5).
 *
 * Real-time token tracking with progressive interventions. A safety margin is
 * applied so the effective ceiling is below the raw budget, leaving headroom
 * for the final summary.
 */

import type { SubAgentState } from './state.js';

export type BudgetLevel = 'monitor' | 'watch' | 'warn' | 'critical' | 'force_wrap' | 'exhausted';

export interface BudgetVerdict {
  level: BudgetLevel;
  fraction: number;
  /** True once new tool calls must stop. */
  stop: boolean;
  message?: string;
}

export class TokenBudgetManager {
  constructor(private readonly safetyMargin: number) {}

  /** Add token cost to the agent and return the resulting budget verdict. */
  consume(state: SubAgentState, tokens: number): BudgetVerdict {
    state.tokensUsed += tokens;
    return this.evaluate(state);
  }

  evaluate(state: SubAgentState): BudgetVerdict {
    const effectiveBudget = state.tokensBudget * (1 - this.safetyMargin);
    const fraction = effectiveBudget > 0 ? state.tokensUsed / effectiveBudget : 1;

    if (fraction >= 1) {
      return {
        level: 'exhausted',
        fraction,
        stop: true,
        message:
          'Token budget exhausted. Tool call chain terminated. Return all findings collected so far ' +
          'and mark the task partial-complete, listing what was not investigated.',
      };
    }
    if (fraction >= 0.9) {
      return {
        level: 'force_wrap',
        fraction,
        stop: true,
        message:
          'Token budget at 90%. Stop all new tool calls. Summarize all findings discovered so far and ' +
          'mark the task as partial-complete. Include what was not investigated.',
      };
    }
    if (fraction >= 0.8) {
      return {
        level: 'critical',
        fraction,
        stop: false,
        message:
          'You are at 85% of your task token budget. Complete the current step only. ' +
          'Begin preparing a partial findings summary.',
      };
    }
    if (fraction >= 0.7) {
      return {
        level: 'warn',
        fraction,
        stop: false,
        message:
          'You are at 70% of your task token budget. Prioritize the highest-impact remaining step. ' +
          'Skip low-confidence branches. Do not open new sub-investigations.',
      };
    }
    if (fraction >= 0.5) {
      return { level: 'watch', fraction, stop: false };
    }
    return { level: 'monitor', fraction, stop: false };
  }
}
