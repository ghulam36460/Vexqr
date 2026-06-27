/**
 * Deterministic tool-output simulator for dry-run / offline mode.
 *
 * Produces realistic raw output for common security tools so the full pipeline
 * (router → execution → parser → supervisor) can be exercised without installing
 * or running real tools. When real execution is enabled this module is bypassed.
 */

export function simulateToolOutput(tool: string, params: Record<string, unknown>): string {
  const host = String(params.host ?? params.target ?? 'scanme.nmap.org');
  switch (tool) {
    case 'nmap':
      return [
        `Starting Nmap 7.94 ( https://nmap.org )`,
        `Nmap scan report for ${host} (45.33.32.156)`,
        `Host is up (0.12s latency).`,
        `PORT     STATE SERVICE     VERSION`,
        `22/tcp   open  ssh         OpenSSH 6.6.1p1`,
        `80/tcp   open  http        Apache httpd 2.4.7`,
        `443/tcp  open  ssl/http    Apache httpd 2.4.7`,
        `9929/tcp open  nping-echo  Nping echo`,
        `Service detection performed.`,
      ].join('\n');
    case 'gobuster':
    case 'ffuf':
      return [
        `===============================================================`,
        `/admin                (Status: 301) [Size: 312]`,
        `/login                (Status: 200) [Size: 1543]`,
        `/api                  (Status: 200) [Size: 88]`,
        `/.git                 (Status: 403) [Size: 277]`,
        `===============================================================`,
      ].join('\n');
    case 'nuclei':
      return [
        JSON.stringify({ 'template-id': 'apache-version-detect', host, info: { severity: 'info' } }),
        JSON.stringify({ 'template-id': 'CVE-2021-41773', host, info: { severity: 'critical' } }),
      ].join('\n');
    case 'nikto':
      return [
        `- Nikto v2.5.0`,
        `+ Server: Apache/2.4.7`,
        `+ OSVDB-3268: /admin/: Directory indexing found.`,
        `+ /login: Admin login page identified.`,
      ].join('\n');
    case 'ghidra':
      return [
        `Ghidra headless analysis complete.`,
        `Functions discovered: 142`,
        `Entry point: 0x00401000`,
        `Suspicious call: system() at 0x00401a3f`,
        `String reference: "/bin/sh"`,
      ].join('\n');
    case 'subfinder':
      return [`www.${host}`, `mail.${host}`, `dev.${host}`, `api.${host}`].join('\n');
    default:
      return `[simulated output for '${tool}' against ${host}] no findings parser matched; raw passthrough.`;
  }
}
