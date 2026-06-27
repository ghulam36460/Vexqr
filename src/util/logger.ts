/** Minimal structured, leveled logger. Zero dependencies. */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_ORDER: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 };

const COLORS: Record<LogLevel, string> = {
  debug: '\x1b[90m',
  info: '\x1b[36m',
  warn: '\x1b[33m',
  error: '\x1b[31m',
};
const RESET = '\x1b[0m';

let threshold: LogLevel = (process.env.VEXQR_LOG_LEVEL as LogLevel) || 'info';
const useColor = process.stdout.isTTY && process.env.NO_COLOR === undefined;

export function setLogLevel(level: LogLevel): void {
  threshold = level;
}

function emit(level: LogLevel, scope: string, msg: string, meta?: unknown): void {
  if (LEVEL_ORDER[level] < LEVEL_ORDER[threshold]) return;
  const ts = new Date().toISOString();
  const tag = level.toUpperCase().padEnd(5);
  const head = useColor ? `${COLORS[level]}${tag}${RESET}` : tag;
  const line = `${ts} ${head} [${scope}] ${msg}`;
  const stream = level === 'error' || level === 'warn' ? process.stderr : process.stdout;
  if (meta !== undefined) {
    stream.write(`${line} ${safeJson(meta)}\n`);
  } else {
    stream.write(`${line}\n`);
  }
}

function safeJson(v: unknown): string {
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export class Logger {
  constructor(private readonly scope: string) {}
  debug(msg: string, meta?: unknown): void {
    emit('debug', this.scope, msg, meta);
  }
  info(msg: string, meta?: unknown): void {
    emit('info', this.scope, msg, meta);
  }
  warn(msg: string, meta?: unknown): void {
    emit('warn', this.scope, msg, meta);
  }
  error(msg: string, meta?: unknown): void {
    emit('error', this.scope, msg, meta);
  }
}

export function createLogger(scope: string): Logger {
  return new Logger(scope);
}
