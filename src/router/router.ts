/**
 * Layer 2 — Task Router & Dispatcher.
 *
 * Receives a ToolCall, runs the routing decision algorithm, then dispatches to
 * L3 (MCP) or L4 (Terminal). All calls pass through the event bus. The
 * supervisor observes everything via beforeCall / afterResult hooks supplied by
 * the orchestrator — the router stays focused on dispatch.
 *
 * NOTE: The security layer (scope enforcement, risk gating, audit) is owned and
 * implemented separately by the security team per their own policies and the
 * legal requirements of the relevant jurisdictions. It is intentionally NOT
 * part of this codebase and must not be re-added here.
 */

import { bus } from '../core/events.js';
import { McpEngine } from '../mcp/mcpEngine.js';
import { TerminalEngine } from '../terminal/ptyEngine.js';
import type { ToolCall, ToolResult, Target } from '../core/types.js';

export interface RouterDeps {
  mcp: McpEngine;
  terminal: TerminalEngine;
}

export class TaskRouter {
  constructor(private readonly deps: RouterDeps) {}

  async dispatch(call: ToolCall, _target: Target): Promise<ToolResult> {
    bus.emit('tool:call', call);

    // Routing decision: MCP first, terminal fallback.
    const result = this.deps.mcp.canHandle(call.tool)
      ? await this.deps.mcp.call(call)
      : await this.deps.terminal.call(call);

    bus.emit('tool:result', result);
    return result;
  }
}
