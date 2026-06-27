/**
 * Layer 4 — Terminal Automation Engine.
 *
 * Wraps ANY CLI security tool so an AI client can use it as if it were a real
 * MCP server (the "mock MCP interface"). For interactive tools (msfconsole,
 * sqlmap --wizard) a real PTY is required; production wires node-pty here.
 *
 * To keep the platform dependency-light and runnable offline, this engine uses
 * child_process for non-interactive tools and falls back to the simulator in
 * dry-run mode. The interface is identical to McpEngine.call(), so the router
 * and supervisor cannot tell which route executed a tool.
 */

import { spawn } from 'node:child_process';
import { createLogger } from '../util/logger.js';
import { estimateTokens } from '../util/ids.js';
import { AutoInstaller } from './installer.js';
import { parseToolOutput } from './parser.js';
import { simulateToolOutput } from './simulator.js';
import { buildArgv } from './argv.js';
import type { ToolCall, ToolResult } from '../core/types.js';

const log = createLogger('pty-engine');

export class TerminalEngine {
  constructor(
    private readonly installer: AutoInstaller,
    private readonly dryRun: boolean,
  ) {}

  /** L4 is the universal fallback — it can attempt any tool. */
  canHandle(_tool: string): boolean {
    return true;
  }

  async call(call: ToolCall): Promise<ToolResult> {
    const start = Date.now();
    const tool = call.tool.toLowerCase();

    // 1. Ensure the tool exists (auto-install cascade).
    const install = this.installer.ensure(tool);
    if (!install.installed) {
      return {
        callId: call.callId,
        tool,
        route: 'terminal',
        status: 'error',
        artifacts: [],
        output: '',
        errors: [install.error ?? 'tool unavailable', install.manualHint ?? ''],
        tokenCost: 0,
        durationMs: Date.now() - start,
      };
    }

    // 2. Execute (or simulate) and capture output.
    let raw: string;
    let status: ToolResult['status'] = 'ok';
    if (this.dryRun || install.alreadyPresent === false) {
      // In dry-run, or when we only "would have" installed, simulate output.
      raw = simulateToolOutput(tool, call.params);
    } else {
      try {
        raw = await this.exec(tool, call);
      } catch (err) {
        raw = '';
        status = (err as Error).message === 'timeout' ? 'timeout' : 'error';
      }
    }

    // 3. Parse raw output → structured artifacts (the mock MCP envelope).
    const artifacts = status === 'ok' ? parseToolOutput(tool, raw) : [];
    log.info(`terminal call '${tool}' -> ${status}, ${artifacts.length} artifacts`);

    return {
      callId: call.callId,
      tool,
      route: 'terminal',
      status,
      artifacts,
      output: raw,
      errors: status === 'ok' ? [] : [`tool '${tool}' exited with ${status}`],
      tokenCost: estimateTokens(raw),
      durationMs: Date.now() - start,
    };
  }

  /** Run a non-interactive tool via child_process with a timeout. */
  private exec(tool: string, call: ToolCall): Promise<string> {
    const argv = buildArgv(tool, call.params);
    const timeoutMs = Number(call.params.timeoutMs ?? 120_000);

    return new Promise<string>((resolveP, rejectP) => {
      const child = spawn(tool, argv, { shell: false });
      let out = '';
      let err = '';
      const timer = setTimeout(() => {
        child.kill('SIGTERM');
        rejectP(new Error('timeout'));
      }, timeoutMs);

      child.stdout.on('data', (d) => (out += d.toString()));
      child.stderr.on('data', (d) => (err += d.toString()));
      child.on('error', (e) => {
        clearTimeout(timer);
        rejectP(e);
      });
      child.on('close', () => {
        clearTimeout(timer);
        resolveP(out || err);
      });
    });
  }
}
