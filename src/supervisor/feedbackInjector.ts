/**
 * Feedback Injector (Supervisor sub-component 8.2.6).
 *
 * Delivers corrective feedback to a sub-agent through ITS OWN native channel:
 *   - API clients  -> mid-conversation system message
 *   - CLI clients  -> stdin write to the subprocess
 *   - MCP agents   -> tool_result with isError=true
 *   - IDE agents   -> extension / MCP error channel
 *
 * Every message is ACTIONABLE: (1) what was detected, (2) what it means,
 * (3) a specific recommended next action. The injector is delegated the actual
 * delivery via the adapter; here we format and route.
 */

import { createLogger } from '../util/logger.js';
import { bus } from '../core/events.js';
import type { SourceClient } from '../core/types.js';

const log = createLogger('feedback');

export type InjectionChannel = 'system_message' | 'stdin' | 'tool_error' | 'ide_message';

export interface Feedback {
  agentId: string;
  reason: string;
  message: string;
}

/** Map each client to the channel used to reach it. */
export function channelFor(client: SourceClient): InjectionChannel {
  switch (client) {
    case 'claude_api':
    case 'gemini_cli':
    case 'custom':
      return 'system_message';
    case 'claude_code':
    case 'codex':
      return 'stdin';
    case 'copilot':
    case 'gitlab_duo':
    case 'cursor':
      return 'ide_message';
    default:
      return 'tool_error';
  }
}

export class FeedbackInjector {
  /**
   * Deliver feedback. Returns the formatted payload that the adapter will hand
   * to the worker AI (e.g. as a tool_result with isError=true). Emits an event
   * so the audit log records every intervention.
   */
  inject(client: SourceClient, fb: Feedback): { channel: InjectionChannel; payload: string } {
    const channel = channelFor(client);
    const payload = `[SUPERVISOR:${fb.reason}] ${fb.message}`;
    log.info(`inject -> ${client} via ${channel}: ${fb.reason}`);
    bus.emit('supervisor:feedback', { agentId: fb.agentId, reason: fb.reason, message: fb.message });
    return { channel, payload };
  }
}
