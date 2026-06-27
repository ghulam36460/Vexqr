/** Strip ANSI escape / terminal control sequences from raw PTY output. */

// eslint-disable-next-line no-control-regex
const ANSI_RE = /[\u001B\u009B][[\]()#;?]*(?:(?:\d{1,4}(?:;\d{0,4})*)?[0-9A-PRZcf-ntqry=><~])/g;

export function stripAnsi(input: string): string {
  return input.replace(ANSI_RE, '');
}
