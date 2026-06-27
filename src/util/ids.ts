/** ID generation + token estimation helpers. */

import { randomUUID, createHash } from 'node:crypto';

export function uuid(): string {
  return randomUUID();
}

/** Short, human-friendly id for agents/sessions. */
export function shortId(prefix = ''): string {
  const s = randomUUID().split('-')[0];
  return prefix ? `${prefix}_${s}` : s;
}

export function sha256(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

/**
 * Approximate token count without pulling in a tokenizer dependency.
 *
 * Real adapters override this with the client's native tokenizer
 * (cl100k_base for Claude, o200k_base for GPT-4o, SentencePiece for Gemini).
 * The ~4 chars/token heuristic is intentionally conservative; the budget
 * manager additionally applies a safety margin on top of this.
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / 4);
}
