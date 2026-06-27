/**
 * Layer 4 — Output Parser.
 *
 * Two-pass parsing of messy terminal output into structured Artifacts:
 *   Pass 1 — Known Format Library: regex/format parsers for common tools.
 *   Pass 2 — LLM Fallback: when no pattern matches, a small model parses it.
 *            (stubbed here; wired to a fast model in production.)
 *
 * The parsed artifacts feed the supervisor's progress scorer and the final report.
 */

import { stripAnsi } from '../util/ansi.js';
import type { Artifact } from '../core/types.js';

type ParserFn = (text: string) => Artifact[];

const now = () => Date.now();

const NMAP_PORT = /^(\d{1,5})\/tcp\s+open\s+(\S+)(?:\s+(.*))?$/;
const GOBUSTER_LINE = /^(\/\S+)\s+\(Status:\s*(\d{3})\)/;
const NUCLEI_SEVERITY = /"severity"\s*:\s*"(\w+)"/;
const NUCLEI_TEMPLATE = /"template-id"\s*:\s*"([^"]+)"/;
const CVE = /CVE-\d{4}-\d{4,7}/g;
const IPV4 = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;

const KNOWN: Record<string, ParserFn> = {
  nmap(text) {
    const out: Artifact[] = [];
    for (const line of text.split('\n')) {
      const m = line.trim().match(NMAP_PORT);
      if (m) {
        out.push({ kind: 'port', value: m[1], source: 'nmap', detail: `${m[2]} ${m[3] ?? ''}`.trim(), discoveredAt: now() });
        out.push({ kind: 'service', value: m[2], source: 'nmap', detail: `port ${m[1]}`, discoveredAt: now() });
      }
    }
    for (const ip of text.match(IPV4) ?? []) {
      out.push({ kind: 'host', value: ip, source: 'nmap', discoveredAt: now() });
    }
    return out;
  },

  gobuster(text) {
    const out: Artifact[] = [];
    for (const line of text.split('\n')) {
      const m = line.trim().match(GOBUSTER_LINE);
      if (m) out.push({ kind: 'path', value: m[1], source: 'gobuster', detail: `status ${m[2]}`, discoveredAt: now() });
    }
    return out;
  },

  nuclei(text) {
    const out: Artifact[] = [];
    for (const line of text.split('\n')) {
      if (!line.trim()) continue;
      const tpl = line.match(NUCLEI_TEMPLATE)?.[1];
      const sev = line.match(NUCLEI_SEVERITY)?.[1] ?? 'info';
      if (tpl) {
        out.push({ kind: 'finding', value: tpl, source: 'nuclei', detail: `severity=${sev}`, discoveredAt: now() });
      }
    }
    return out;
  },

  nikto(text) {
    const out: Artifact[] = [];
    for (const line of text.split('\n')) {
      const t = line.trim();
      if (t.startsWith('+') && t.length > 3) {
        out.push({ kind: 'finding', value: t.replace(/^\+\s*/, ''), source: 'nikto', discoveredAt: now() });
      }
    }
    return out;
  },

  subfinder(text) {
    return text
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(l))
      .map((d) => ({ kind: 'domain' as const, value: d, source: 'subfinder', discoveredAt: now() }));
  },

  ghidra(text) {
    const out: Artifact[] = [];
    for (const line of text.split('\n')) {
      const t = line.trim();
      if (/suspicious|system\(|\/bin\/sh|string reference/i.test(t)) {
        out.push({ kind: 'finding', value: t, source: 'ghidra', discoveredAt: now() });
      }
    }
    return out;
  },
};

// Aliases that share a parser.
KNOWN.ffuf = KNOWN.gobuster;

/** Parse raw tool output into structured artifacts. */
export function parseToolOutput(tool: string, raw: string): Artifact[] {
  const text = stripAnsi(raw);
  const parser = KNOWN[tool.toLowerCase()];
  if (parser) {
    const artifacts = parser(text);
    if (artifacts.length > 0) return dedup(artifacts);
  }
  // Pass 2 fallback: generic extraction (stands in for the LLM parser).
  return dedup(genericParse(text, tool));
}

/** Generic best-effort extraction when no known parser matches. */
function genericParse(text: string, tool: string): Artifact[] {
  const out: Artifact[] = [];
  for (const cve of text.match(CVE) ?? []) {
    out.push({ kind: 'cve', value: cve, source: tool, discoveredAt: now() });
  }
  for (const ip of text.match(IPV4) ?? []) {
    out.push({ kind: 'host', value: ip, source: tool, discoveredAt: now() });
  }
  return out;
}

function dedup(items: Artifact[]): Artifact[] {
  const seen = new Set<string>();
  const out: Artifact[] = [];
  for (const a of items) {
    const key = `${a.kind}:${a.value}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(a);
    }
  }
  return out;
}
