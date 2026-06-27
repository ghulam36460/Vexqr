/**
 * Human Escalation Manager (Supervisor sub-component 8.2.7).
 *
 * Five conditions pause a sub-agent and hand control to a human:
 *   1. HIGH_RISK tool request
 *   2. Scope boundary approach / breach
 *   3. Loop escalation (loop fired N times, auto-correction failed)
 *   4. Novel critical finding
 *   5. Sub-agent contradiction of the phase plan
 */

import { createLogger } from '../util/logger.js';
import { bus } from '../core/events.js';

const log = createLogger('escalation');

export type EscalationReason =
  | 'HIGH_RISK'
  | 'SCOPE_BOUNDARY'
  | 'LOOP_ESCALATION'
  | 'CRITICAL_FINDING'
  | 'PLAN_CONTRADICTION';

export interface EscalationRequest {
  agentId: string;
  reason: EscalationReason;
  summary: string;
  /** Options presented to the human operator. */
  options: string[];
}

/** Async hook a host app implements to actually ask a human. */
export interface HumanGate {
  (req: EscalationRequest): Promise<'approve' | 'deny'>;
}

export class EscalationManager {
  constructor(private readonly gate: HumanGate) {}

  async escalate(req: EscalationRequest): Promise<'approve' | 'deny'> {
    log.warn(`escalating to human: ${req.reason} (agent ${req.agentId})`);
    bus.emit('supervisor:escalate', { agentId: req.agentId, reason: req.reason, summary: req.summary });
    const decision = await this.gate(req);
    log.info(`human decision for ${req.reason}: ${decision}`);
    return decision;
  }
}
