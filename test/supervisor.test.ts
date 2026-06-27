import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LoopDetector } from '../src/supervisor/loopDetector.js';
import { ProgressScorer } from '../src/supervisor/progressScorer.js';
import { TokenBudgetManager } from '../src/supervisor/tokenBudget.js';
import { createState, recordCall, mergeArtifacts } from '../src/supervisor/state.js';
import type { ToolCall, Artifact } from '../src/core/types.js';

function call(tool: string, host: string): ToolCall {
  return { callId: 't', agentId: 'a', taskId: 'k', phase: 'enumeration', tool, params: { host } };
}

test('loop detector fires after threshold of identical calls', () => {
  const det = new LoopDetector(3);
  const state = createState('a', 'k', 'enumeration', 1000);
  let last;
  for (let i = 0; i < 3; i++) {
    const c = call('gobuster', 'host.test');
    recordCall(state, c);
    last = det.check(state, c);
  }
  assert.equal(last!.looping, true);
  assert.match(last!.message!, /gobuster/);
});

test('loop detector is more tolerant for recon tools', () => {
  const det = new LoopDetector(3);
  const state = createState('a', 'k', 'recon', 1000);
  // 3 identical nmap calls should NOT fire (recon threshold = base + 2 = 5).
  let v;
  for (let i = 0; i < 3; i++) {
    const c = call('nmap', 'host.test');
    recordCall(state, c);
    v = det.check(state, c);
  }
  assert.equal(v!.looping, false);
});

test('progress scorer flags low productivity after window', () => {
  const scorer = new ProgressScorer(5);
  const state = createState('a', 'k', 'vuln_scan', 1000);
  mergeArtifacts(state, [{ kind: 'finding', value: 'x', discoveredAt: Date.now() }]);
  state.callsSinceLastArtifact = 5;
  const v = scorer.check(state);
  assert.equal(v.productive, false);
  assert.equal(v.phaseComplete, true);
});

test('token budget escalates through levels with safety margin', () => {
  const mgr = new TokenBudgetManager(0.15);
  const state = createState('a', 'k', 'recon', 1000); // effective budget = 850
  assert.equal(mgr.consume(state, 400).level, 'monitor'); // 400/850 = 0.47 -> monitor
  const state2 = createState('b', 'k', 'recon', 1000);
  assert.equal(mgr.consume(state2, 620).level, 'warn'); // 0.73
  const state3 = createState('c', 'k', 'recon', 1000);
  const v = mgr.consume(state3, 800); // 0.94 -> force_wrap
  assert.equal(v.level, 'force_wrap');
  assert.equal(v.stop, true);
});

test('mergeArtifacts dedups and tracks novelty', () => {
  const state = createState('a', 'k', 'recon', 1000);
  const a: Artifact[] = [
    { kind: 'port', value: '22', discoveredAt: 1 },
    { kind: 'port', value: '22', discoveredAt: 2 },
    { kind: 'port', value: '80', discoveredAt: 3 },
  ];
  const novel = mergeArtifacts(state, a);
  assert.equal(novel.length, 2);
  assert.equal(state.artifacts.length, 2);
  assert.equal(state.callsSinceLastArtifact, 0);
});
