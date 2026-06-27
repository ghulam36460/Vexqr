/**
 * Typed, in-process event bus.
 *
 * The Supervisor (L5) subscribes to ToolCall / ToolResult events so it can
 * observe everything without being on the critical execution path. Using a
 * single bus keeps the layers decoupled: the router emits, the supervisor
 * listens, the audit log listens — none of them import each other.
 */

import { EventEmitter } from 'node:events';
import type { ToolCall, ToolResult, Artifact, Phase } from './types.js';

export interface EventMap {
  'tool:call': ToolCall;
  'tool:result': ToolResult;
  'artifact:new': { taskId: string; agentId: string; artifact: Artifact };
  'phase:enter': { taskId: string; phase: Phase };
  'phase:complete': { taskId: string; phase: Phase };
  'supervisor:feedback': { agentId: string; reason: string; message: string };
  'supervisor:escalate': { agentId: string; reason: string; summary: string };
  'budget:level': { agentId: string; level: string; tokensUsed: number; tokensBudget: number };
  'task:complete': { taskId: string };
}

type Handler<T> = (payload: T) => void;

export class TypedEventBus {
  private readonly emitter = new EventEmitter();

  constructor() {
    // Security operations can spawn many concurrent listeners.
    this.emitter.setMaxListeners(100);
  }

  on<K extends keyof EventMap>(event: K, handler: Handler<EventMap[K]>): void {
    this.emitter.on(event, handler as (payload: unknown) => void);
  }

  off<K extends keyof EventMap>(event: K, handler: Handler<EventMap[K]>): void {
    this.emitter.off(event, handler as (payload: unknown) => void);
  }

  emit<K extends keyof EventMap>(event: K, payload: EventMap[K]): void {
    this.emitter.emit(event, payload);
  }
}

/** Shared singleton bus for a single-host deployment. */
export const bus = new TypedEventBus();
