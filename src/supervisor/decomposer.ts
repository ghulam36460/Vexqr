/**
 * Task Decomposer & Execution Planner (Supervisor sub-component 8.2.1).
 *
 * Breaks a high-level user request into a phase-ordered plan (a DAG, here a
 * linear chain since security phases are sequential with dependencies). Each
 * node carries a tool whitelist, a token budget slice and a sub-agent profile.
 *
 * Phase selection is inferred from the natural-language goal so a non-technical
 * user never has to name a phase or a tool.
 */

import type { Phase, TaskObject } from '../core/types.js';
import type { SentinelConfig } from '../core/config.js';

export interface PlanNode {
  phase: Phase;
  /** Tools this phase's sub-agent is allowed to call. */
  toolWhitelist: string[];
  tokenBudget: number;
  /** System-prompt persona for the sub-agent running this phase. */
  profile: string;
  requiresHumanGate: boolean;
}

const PHASE_TOOLS: Record<Phase, string[]> = {
  recon: ['nmap', 'subfinder', 'amass', 'shodan', 'theharvester'],
  enumeration: ['gobuster', 'ffuf', 'enum4linux', 'smbclient', 'ldapsearch'],
  vuln_scan: ['nuclei', 'nikto', 'openvas', 'wpscan'],
  exploit: ['metasploit', 'sqlmap', 'hydra'],
  analysis: ['ghidra', 'radare2', 'binwalk', 'yara'],
  post_exploit: ['volatility', 'cyberchef'],
  report: [],
};

const PHASE_PROFILES: Record<Phase, string> = {
  recon: 'Recon specialist: map the attack surface using passive and active discovery. Do not exploit.',
  enumeration: 'Enumeration specialist: enumerate services and content on discovered hosts. Do not exploit.',
  vuln_scan: 'Vulnerability analyst: identify and triage weaknesses. Do not exploit without authorization.',
  exploit: 'Exploitation specialist: validate vulnerabilities. Every action requires a human gate.',
  analysis: 'Reverse engineering / analysis specialist for binaries and artifacts.',
  post_exploit: 'Post-exploitation analyst: analyze collected data. Sequential, careful operations.',
  report: 'Reporting agent: aggregate all findings into a clear, prioritized report.',
};

/** Keyword → phases the request likely needs. */
function inferPhases(input: string): Phase[] {
  const t = input.toLowerCase();

  if (/(reverse engineer|\bexe\b|binary|ghidra|decompile|malware|debug)/.test(t)) {
    return ['analysis', 'report'];
  }
  if (/(full|complete|thorough|pentest|penetration|assessment|audit)/.test(t)) {
    return ['recon', 'enumeration', 'vuln_scan', 'report'];
  }
  if (/(exploit|gain access|pop a shell|break in)/.test(t)) {
    return ['recon', 'enumeration', 'vuln_scan', 'exploit', 'report'];
  }
  if (/(secure|vulnerab|owasp|sql injection|xss|safe|check.*app|web app)/.test(t)) {
    return ['recon', 'enumeration', 'vuln_scan', 'report'];
  }
  // Sensible default for an ambiguous goal.
  return ['recon', 'vuln_scan', 'report'];
}

export class TaskDecomposer {
  constructor(private readonly config: SentinelConfig) {}

  plan(task: TaskObject): PlanNode[] {
    const phases = inferPhases(task.naturalInput);
    const totalBudget = task.constraints.maxTokens;

    // Re-normalize the phase-budget fractions across only the selected phases.
    const fractions = phases.map((p) => this.config.phaseBudget[p] ?? 0.1);
    const fracSum = fractions.reduce((a, b) => a + b, 0) || 1;

    return phases.map((phase, i) => ({
      phase,
      toolWhitelist: PHASE_TOOLS[phase],
      tokenBudget: Math.floor((fractions[i] / fracSum) * totalBudget),
      profile: PHASE_PROFILES[phase],
      requiresHumanGate: phase === 'exploit',
    }));
  }

  /**
   * Re-planning: if a phase produced far more attack surface than expected,
   * grow the budget of the remaining phases proportionally.
   */
  reallocate(nodes: PlanNode[], fromIndex: number, surfaceMultiplier: number): void {
    if (surfaceMultiplier <= 1) return;
    for (let i = fromIndex + 1; i < nodes.length; i++) {
      nodes[i].tokenBudget = Math.floor(nodes[i].tokenBudget * Math.min(surfaceMultiplier, 3));
    }
  }
}
