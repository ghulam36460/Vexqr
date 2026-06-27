/**
 * Layer 4 — Auto-Installer Cascade.
 *
 * When a tool is required but missing, try installation methods in order until
 * one succeeds: apt → pip → cargo → go → npm → brew → winget → git+make → docker.
 * On total failure, return a structured error with manual instructions.
 *
 * Detection is real (which/where + OS detection); actual installation is gated
 * behind dryRun so the platform never mutates a host during tests/demos.
 */

import { execFileSync, execSync } from 'node:child_process';
import { platform } from 'node:os';
import { existsSync, readFileSync } from 'node:fs';
import { createLogger } from '../util/logger.js';

const log = createLogger('installer');

export type InstallMethod = 'apt' | 'pip' | 'cargo' | 'go' | 'npm' | 'brew' | 'winget' | 'git' | 'docker';

export interface InstallPlan {
  tool: string;
  method: InstallMethod;
  command: string;
}

export interface InstallResult {
  installed: boolean;
  method?: InstallMethod;
  alreadyPresent: boolean;
  error?: string;
  manualHint?: string;
}

/** Map known tools to their preferred install command per method. */
const INSTALL_MATRIX: Record<string, Partial<Record<InstallMethod, string>>> = {
  nmap: { apt: 'apt-get install -y nmap', brew: 'brew install nmap', winget: 'winget install Insecure.Nmap' },
  nikto: { apt: 'apt-get install -y nikto', brew: 'brew install nikto' },
  gobuster: { apt: 'apt-get install -y gobuster', go: 'go install github.com/OJ/gobuster/v3@latest' },
  ffuf: { apt: 'apt-get install -y ffuf', go: 'go install github.com/ffuf/ffuf/v2@latest' },
  nuclei: { go: 'go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest', pip: 'pip install nuclei-cli' },
  subfinder: { go: 'go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest' },
  feroxbuster: { cargo: 'cargo install feroxbuster' },
  rustscan: { cargo: 'cargo install rustscan' },
  hydra: { apt: 'apt-get install -y hydra', brew: 'brew install hydra' },
  sqlmap: { apt: 'apt-get install -y sqlmap', pip: 'pip install sqlmap' },
};

const CASCADE_ORDER: InstallMethod[] = ['apt', 'pip', 'cargo', 'go', 'npm', 'brew', 'winget', 'git', 'docker'];

export class AutoInstaller {
  constructor(private readonly dryRun: boolean) {}

  /** Is the tool binary already on PATH? */
  isInstalled(tool: string): boolean {
    const probe = platform() === 'win32' ? 'where' : 'which';
    try {
      execFileSync(probe, [tool], { stdio: 'ignore' });
      return true;
    } catch {
      return false;
    }
  }

  /** Which install methods are usable on this host right now. */
  availableMethods(): Set<InstallMethod> {
    const found = new Set<InstallMethod>();
    const checks: Array<[InstallMethod, string]> = [
      ['apt', 'apt-get'],
      ['pip', 'pip'],
      ['cargo', 'cargo'],
      ['go', 'go'],
      ['npm', 'npm'],
      ['brew', 'brew'],
      ['winget', 'winget'],
      ['git', 'git'],
      ['docker', 'docker'],
    ];
    const probe = platform() === 'win32' ? 'where' : 'which';
    for (const [method, bin] of checks) {
      try {
        execFileSync(probe, [bin], { stdio: 'ignore' });
        found.add(method);
      } catch {
        /* not available */
      }
    }
    return found;
  }

  /** Detect the host OS family to bias the cascade (apt vs brew vs winget). */
  detectOs(): 'debian' | 'macos' | 'windows' | 'other' {
    const p = platform();
    if (p === 'darwin') return 'macos';
    if (p === 'win32') return 'windows';
    if (existsSync('/etc/debian_version')) return 'debian';
    try {
      const rel = readFileSync('/etc/os-release', 'utf8');
      if (/debian|ubuntu|kali/i.test(rel)) return 'debian';
    } catch {
      /* ignore */
    }
    return 'other';
  }

  ensure(tool: string): InstallResult {
    const t = tool.toLowerCase();
    if (this.isInstalled(t)) {
      return { installed: true, alreadyPresent: true };
    }

    const available = this.availableMethods();
    const matrix = INSTALL_MATRIX[t] ?? {};

    for (const method of CASCADE_ORDER) {
      if (!available.has(method)) continue;
      const cmd = matrix[method];
      if (!cmd) continue;

      if (this.dryRun) {
        log.info(`[dry-run] would install '${t}' via ${method}: ${cmd}`);
        return { installed: true, alreadyPresent: false, method };
      }
      try {
        log.info(`installing '${t}' via ${method}`);
        execSync(cmd, { stdio: 'inherit' });
        if (this.isInstalled(t)) return { installed: true, alreadyPresent: false, method };
      } catch (err) {
        log.warn(`install via ${method} failed: ${String(err)}`);
      }
    }

    return {
      installed: false,
      alreadyPresent: false,
      error: `all install methods failed for '${t}'`,
      manualHint: `Install '${t}' manually. Available methods on this host: ${[...available].join(', ') || 'none'}.`,
    };
  }
}
