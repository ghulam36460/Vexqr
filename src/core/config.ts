/**
 * Configuration loading + validation.
 *
 * User settings come from config.yaml (human-readable) and scope rules from
 * scope.json (industry convention). Both are validated against sane defaults
 * so a missing or partial file never crashes the platform.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import YAML from 'yaml';
import { createLogger } from '../util/logger.js';

const log = createLogger('config');

export interface SupervisorConfig {
  /** Consecutive near-identical calls before a loop fires (recon is more tolerant). */
  loopThreshold: number;
  /** Calls without a novel artifact before low-productivity fires. */
  productivityWindow: number;
  /** Loop fires on the same task before escalating to a human. */
  loopEscalationLimit: number;
  /** Safety margin applied to all token budget math (0.15 = reserve 15%). */
  tokenSafetyMargin: number;
}

export interface AegixConfig {
  defaultMaxTokens: number;
  /** Per-phase fraction of the total token budget. Must sum to ~1.0. */
  phaseBudget: Record<string, number>;
  supervisor: SupervisorConfig;
  /** When true, no real tools run; the terminal/MCP layers simulate output. */
  dryRun: boolean;
  registryPath: string;
}

export const DEFAULT_CONFIG: AegixConfig = {
  defaultMaxTokens: 200_000,
  phaseBudget: {
    recon: 0.15,
    enumeration: 0.2,
    vuln_scan: 0.25,
    exploit: 0.2,
    analysis: 0.05,
    post_exploit: 0.05,
    report: 0.1,
  },
  supervisor: {
    loopThreshold: 3,
    productivityWindow: 5,
    loopEscalationLimit: 3,
    tokenSafetyMargin: 0.15,
  },
  dryRun: false,
  registryPath: 'config/registry.json',
};

function deepMerge<T>(base: T, override: Partial<T>): T {
  if (override === undefined || override === null) return base;
  const out: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  for (const [k, v] of Object.entries(override as Record<string, unknown>)) {
    const bv = (base as Record<string, unknown>)[k];
    if (v && typeof v === 'object' && !Array.isArray(v) && bv && typeof bv === 'object') {
      out[k] = deepMerge(bv, v as Record<string, unknown>);
    } else if (v !== undefined) {
      out[k] = v;
    }
  }
  return out as T;
}

export function loadConfig(path = 'config/config.yaml'): AegixConfig {
  const abs = resolve(process.cwd(), path);
  if (!existsSync(abs)) {
    log.warn(`config not found at ${path}, using defaults`);
    return DEFAULT_CONFIG;
  }
  try {
    const raw = readFileSync(abs, 'utf8');
    const parsed = YAML.parse(raw) as Partial<AegixConfig>;
    const merged = deepMerge(DEFAULT_CONFIG, parsed ?? {});
    validate(merged);
    log.info(`loaded config from ${path}`);
    return merged;
  } catch (err) {
    log.error(`failed to parse config, using defaults`, String(err));
    return DEFAULT_CONFIG;
  }
}

function validate(cfg: AegixConfig): void {
  const sum = Object.values(cfg.phaseBudget).reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1) > 0.01) {
    log.warn(`phaseBudget fractions sum to ${sum.toFixed(2)}, expected ~1.0`);
  }
  if (cfg.supervisor.tokenSafetyMargin < 0 || cfg.supervisor.tokenSafetyMargin >= 1) {
    throw new Error('supervisor.tokenSafetyMargin must be in [0, 1)');
  }
}
