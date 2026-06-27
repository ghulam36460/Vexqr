/**
 * Public entry point — assembles all layers into a ready-to-run platform.
 *
 * This is the wiring/composition root. Construct a Vexqr with a config and
 * a set of host callbacks (confirmation + human gate), then call run(goal).
 */

import { loadConfig, type VexqrConfig } from './core/config.js';
import { Orchestrator } from './core/orchestrator.js';
import { TaskRouter } from './router/router.js';
import { McpRegistry } from './mcp/registry.js';
import { McpEngine } from './mcp/mcpEngine.js';
import { TerminalEngine } from './terminal/ptyEngine.js';
import { AutoInstaller } from './terminal/installer.js';
import { Supervisor } from './supervisor/supervisor.js';
import { GenericAdapter } from './adapters/genericAdapter.js';
import type { HumanGate } from './supervisor/escalation.js';
import type { ClientAdapter } from './adapters/types.js';
import type { ResultObject, SourceClient } from './core/types.js';

export * from './core/types.js';
export { loadConfig } from './core/config.js';

export interface VexqrOptions {
  config?: VexqrConfig;
  client?: SourceClient;
  dryRun?: boolean;
  /** Ask a human to confirm running a community/experimental MCP server. */
  confirmMcp?: (prompt: string) => Promise<boolean>;
  /** Human escalation gate. Default: deny. */
  humanGate?: HumanGate;
  /** Demo helper: force a loop on this tool to showcase the supervisor. */
  simulateLoopOn?: string;
  adapter?: ClientAdapter;
}

export class Vexqr {
  readonly config: VexqrConfig;
  private readonly orchestrator: Orchestrator;
  private readonly mcpEngine: McpEngine;

  constructor(opts: VexqrOptions = {}) {
    this.config = opts.config ?? loadConfig();
    if (opts.dryRun !== undefined) this.config.dryRun = opts.dryRun;

    const client: SourceClient = opts.client ?? 'custom';

    // Security layer (scope, risk gating, audit) is intentionally omitted here.
    // It is owned and implemented separately by the security team according to
    // their own policies and the laws of the relevant jurisdictions.

    // L3 — MCP.
    const registry = McpRegistry.load(this.config.registryPath);
    const confirmMcp = opts.confirmMcp ?? (async () => false);
    this.mcpEngine = new McpEngine(registry, this.config.dryRun, confirmMcp);

    // L4 — Terminal.
    const installer = new AutoInstaller(this.config.dryRun);
    const terminal = new TerminalEngine(installer, this.config.dryRun);

    // L2 — Router.
    const router = new TaskRouter({ mcp: this.mcpEngine, terminal });

    // L5 — Supervisor.
    const humanGate: HumanGate = opts.humanGate ?? (async () => 'deny');
    const supervisor = new Supervisor(this.config, client, humanGate);

    // L1 — Adapter.
    const adapter = opts.adapter ?? new GenericAdapter(client, opts.simulateLoopOn);

    this.orchestrator = new Orchestrator({ config: this.config, adapter, router, supervisor });
    this.adapter = adapter;
  }

  private readonly adapter: ClientAdapter;

  /** Run a plain-English goal against a target. */
  async run(goal: string, target: string): Promise<ResultObject> {
    const task = this.adapter.normalize(goal, target);
    const result = await this.orchestrator.run(task);
    this.mcpEngine.shutdown();
    return result;
  }
}
