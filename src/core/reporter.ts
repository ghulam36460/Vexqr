/**
 * Report generator (Reporting phase).
 *
 * Aggregates all collected artifacts into a clear, prioritized summary that a
 * non-technical user can understand. Critical/high findings surface first.
 */

import type { Artifact, Phase } from '../core/types.js';

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

function severityOf(a: Artifact): string {
  const m = a.detail?.match(/severity=(\w+)/i);
  if (m) return m[1].toLowerCase();
  if (a.kind === 'credential') return 'critical';
  if (a.kind === 'cve') return 'high';
  if (a.kind === 'finding') return 'medium';
  return 'info';
}

export function buildSummary(artifacts: Artifact[], phasesCompleted: Phase[]): string {
  if (artifacts.length === 0) {
    return `Assessment complete. Phases run: ${phasesCompleted.join(' → ') || 'none'}. No findings were discovered.`;
  }

  const byKind = new Map<string, Artifact[]>();
  for (const a of artifacts) {
    const list = byKind.get(a.kind) ?? [];
    list.push(a);
    byKind.set(a.kind, list);
  }

  const findings = artifacts
    .filter((a) => a.kind === 'finding' || a.kind === 'cve' || a.kind === 'credential')
    .sort((x, y) => SEVERITY_ORDER.indexOf(severityOf(x)) - SEVERITY_ORDER.indexOf(severityOf(y)));

  const lines: string[] = [];
  lines.push(`Security assessment complete. Phases run: ${phasesCompleted.join(' → ')}.`);
  lines.push('');
  lines.push(`Attack surface discovered:`);
  for (const [kind, list] of byKind) {
    if (kind === 'finding' || kind === 'cve') continue;
    lines.push(`  - ${list.length} ${kind}${list.length > 1 ? 's' : ''}: ${list.slice(0, 8).map((a) => a.value).join(', ')}`);
  }
  lines.push('');
  if (findings.length > 0) {
    lines.push(`Prioritized findings (${findings.length}):`);
    for (const f of findings.slice(0, 20)) {
      lines.push(`  [${severityOf(f).toUpperCase()}] ${f.value}${f.source ? ` (${f.source})` : ''}`);
    }
  } else {
    lines.push('No specific vulnerabilities were flagged. Surface mapping completed.');
  }
  return lines.join('\n');
}
