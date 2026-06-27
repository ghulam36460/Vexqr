#!/usr/bin/env node
/**
 * Sentinel CLI.
 *
 * Usage:
 *   sentinel run "<goal>" --target <host> [--dry-run] [--client <id>]
 *                         [--yes] [--demo-loop <tool>] [--verbose]
 *   sentinel registry
 *
 * The CLI is the reference host application: it wires human confirmation /
 * escalation to interactive stdin prompts.
 */

import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';
import { Sentinel } from '../index.js';
import { loadConfig } from '../core/config.js';
import { McpRegistry } from '../mcp/registry.js';
import { setLogLevel } from '../util/logger.js';
import { bus } from '../core/events.js';
import type { SourceClient } from '../core/types.js';

interface Args {
  command: string;
  goal?: string;
  target: string;
  dryRun: boolean;
  client: SourceClient;
  autoYes: boolean;
  demoLoop?: string;
  verbose: boolean;
}

function parseArgs(argv: string[]): Args {
  const a: Args = {
    command: argv[0] ?? 'help',
    target: 'scanme.nmap.org',
    dryRun: false,
    client: 'custom',
    autoYes: false,
    verbose: false,
  };
  const positional: string[] = [];
  for (let i = 1; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--dry-run') a.dryRun = true;
    else if (t === '--yes' || t === '-y') a.autoYes = true;
    else if (t === '--verbose' || t === '-v') a.verbose = true;
    else if (t === '--target') a.target = argv[++i];
    else if (t === '--client') a.client = argv[++i] as SourceClient;
    else if (t === '--demo-loop') a.demoLoop = argv[++i];
    else positional.push(t);
  }
  if (positional.length) a.goal = positional.join(' ');
  return a;
}

async function prompt(question: string): Promise<boolean> {
  const rl = createInterface({ input: stdin, output: stdout });
  const ans = (await rl.question(question)).trim().toLowerCase();
  rl.close();
  return ans === 'y' || ans === 'yes';
}

function wireLiveLog(): void {
  bus.on('phase:enter', (e) => stdout.write(`\n=== PHASE: ${e.phase.toUpperCase()} ===\n`));
  bus.on('tool:call', (c) => stdout.write(`  → ${c.tool} ${JSON.stringify(c.params)}\n`));
  bus.on('artifact:new', (e) => stdout.write(`    + ${e.artifact.kind}: ${e.artifact.value}\n`));
  bus.on('supervisor:feedback', (f) => stdout.write(`  ⚠ SUPERVISOR [${f.reason}]: ${f.message}\n`));
  bus.on('supervisor:escalate', (e) => stdout.write(`  ⛔ ESCALATION [${e.reason}]: ${e.summary}\n`));
  bus.on('budget:level', (b) => {
    if (b.level !== 'monitor' && b.level !== 'watch') {
      stdout.write(`  $ budget ${b.level}: ${b.tokensUsed}/${b.tokensBudget} tokens\n`);
    }
  });
}

async function cmdRun(args: Args): Promise<void> {
  if (!args.goal) {
    stdout.write('error: provide a goal, e.g. sentinel run "check if my web app is secure" --target example.test\n');
    process.exit(1);
  }
  if (args.verbose) setLogLevel('debug');
  wireLiveLog();

  const confirm = args.autoYes ? async () => true : prompt;
  const sentinel = new Sentinel({
    client: args.client,
    dryRun: args.dryRun,
    simulateLoopOn: args.demoLoop,
    confirmMcp: confirm,
    humanGate: async (req) => {
      stdout.write(`\n  ⛔ HUMAN GATE [${req.reason}]: ${req.summary}\n`);
      const ok = args.autoYes ? false : await confirm('     Approve? [y/N] ');
      return ok ? 'approve' : 'deny';
    },
  });

  stdout.write(`\nGoal: "${args.goal}"\nTarget: ${args.target}\nMode: ${args.dryRun ? 'DRY-RUN (simulated)' : 'LIVE'}\n`);
  const result = await sentinel.run(args.goal, args.target);

  stdout.write(`\n${'='.repeat(60)}\nRESULT (${result.status})\n${'='.repeat(60)}\n`);
  stdout.write(result.summary + '\n\n');
  stdout.write(`Tokens used: ${result.tokensUsed} / ${result.tokensBudget}\n`);
  stdout.write(`Phases: ${result.phasesCompleted.join(' → ')}\n`);
}

function cmdRegistry(): void {
  const cfg = loadConfig();
  const reg = McpRegistry.load(cfg.registryPath);
  stdout.write('Registered MCP tools:\n');
  for (const t of reg.list()) {
    const e = reg.get(t)!;
    stdout.write(`  - ${t} [${e.trustTier}] ${e.transport} ${e.mcpServer}\n`);
  }
}

function help(): void {
  stdout.write(
    [
      'Sentinel — AI-Supervised Cybersecurity Tool Orchestration',
      '',
      'Commands:',
      '  run "<goal>" --target <host> [options]   Run a supervised assessment',
      '  registry                                 List registered MCP tools',
      '',
      'Options for run:',
      '  --target <host>     Target host/URL',
      '  --dry-run           Simulate tools (no real execution/install)',
      '  --client <id>       AI client id (claude_code, gemini_cli, ...)',
      '  --yes, -y           Auto-confirm prompts',
      '  --demo-loop <tool>  Force a loop on <tool> to showcase the supervisor',
      '  --verbose, -v       Debug logging',
      '',
      'Examples:',
      '  sentinel run "check if my web app is secure" --target scanme.nmap.org --dry-run',
      '  sentinel run "full security assessment" --target scanme.nmap.org --dry-run --demo-loop nmap',
    ].join('\n') + '\n',
  );
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  switch (args.command) {
    case 'run':
      await cmdRun(args);
      break;
    case 'registry':
      cmdRegistry();
      break;
    default:
      help();
  }
}

main().catch((err) => {
  process.stderr.write(`fatal: ${err instanceof Error ? err.stack : String(err)}\n`);
  process.exit(1);
});
