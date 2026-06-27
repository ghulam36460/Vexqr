/**
 * Translate structured tool params into a safe argv array for a CLI tool.
 *
 * Using an explicit argv (shell:false) avoids shell injection. Each known tool
 * has a small mapper; unknown tools get a generic flag-mapping fallback.
 */

type ArgvFn = (p: Record<string, unknown>) => string[];

const str = (v: unknown, fallback = ''): string => (v == null ? fallback : String(v));

const MAPPERS: Record<string, ArgvFn> = {
  nmap(p) {
    const args = ['-Pn'];
    if (p.serviceDetection !== false) args.push('-sV');
    if (p.ports) args.push('-p', str(p.ports));
    args.push(str(p.host ?? p.target));
    return args;
  },
  gobuster(p) {
    return ['dir', '-u', str(p.host ?? p.url), '-w', str(p.wordlist, '/usr/share/wordlists/dirb/common.txt')];
  },
  nuclei(p) {
    return ['-u', str(p.host ?? p.url), '-jsonl'];
  },
  nikto(p) {
    return ['-h', str(p.host ?? p.url)];
  },
  subfinder(p) {
    return ['-d', str(p.host ?? p.domain), '-silent'];
  },
};

export function buildArgv(tool: string, params: Record<string, unknown>): string[] {
  const mapper = MAPPERS[tool.toLowerCase()];
  if (mapper) return mapper(params);

  // Generic fallback: --key value for each param, then positional 'target'/'host'.
  const args: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (k === 'host' || k === 'target' || k === 'timeoutMs') continue;
    if (v === true) args.push(`--${k}`);
    else if (v !== false && v != null) args.push(`--${k}`, String(v));
  }
  const target = params.target ?? params.host;
  if (target != null) args.push(String(target));
  return args;
}
