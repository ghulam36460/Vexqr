import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseToolOutput } from '../src/terminal/parser.js';
import { simulateToolOutput } from '../src/terminal/simulator.js';
import { TaskDecomposer } from '../src/supervisor/decomposer.js';
import { DEFAULT_CONFIG } from '../src/core/config.js';
import type { TaskObject } from '../src/core/types.js';

test('nmap output parses into port + service artifacts', () => {
  const raw = simulateToolOutput('nmap', { host: 'scanme.nmap.org' });
  const artifacts = parseToolOutput('nmap', raw);
  const ports = artifacts.filter((a) => a.kind === 'port').map((a) => a.value);
  assert.ok(ports.includes('22'));
  assert.ok(ports.includes('80'));
});

test('nuclei output extracts findings with severity', () => {
  const raw = simulateToolOutput('nuclei', { host: 'x.test' });
  const artifacts = parseToolOutput('nuclei', raw);
  assert.ok(artifacts.some((a) => a.value.includes('CVE-2021-41773')));
});

test('decomposer infers vuln-scan phases for a "is it secure" goal', () => {
  const dec = new TaskDecomposer(DEFAULT_CONFIG);
  const task = {
    naturalInput: 'check if my web app is secure',
    constraints: { maxTokens: 100000 },
  } as unknown as TaskObject;
  const plan = dec.plan(task);
  const phases = plan.map((p) => p.phase);
  assert.deepEqual(phases, ['recon', 'enumeration', 'vuln_scan', 'report']);
  const total = plan.reduce((s, n) => s + n.tokenBudget, 0);
  assert.ok(total <= 100000 && total > 90000);
});

test('decomposer routes a binary/EXE goal to analysis', () => {
  const dec = new TaskDecomposer(DEFAULT_CONFIG);
  const task = { naturalInput: 'help me debug this EXE', constraints: { maxTokens: 50000 } } as unknown as TaskObject;
  const phases = dec.plan(task).map((p) => p.phase);
  assert.deepEqual(phases, ['analysis', 'report']);
});
