# Vexqr

**AI-Supervised Cybersecurity Tool Orchestration Platform.**

Vexqr is a pipeline that connects any AI client (Claude, Gemini, Copilot,
GitLab Duo, Cursor, Codex, or any custom OpenAI-compatible model) to security
tools — via [MCP](https://modelcontextprotocol.io) servers when available, or
via terminal automation as a fallback — and **supervises the worker AI in real
time** so it does not loop, waste tokens, or wander off track.

A user describes a goal in plain English ("check if my web app is secure",
"help me debug this EXE", "run a full security assessment"). Vexqr figures out
which tools are needed, connects or installs them, runs them, and a second AI
supervises the whole operation: detecting loops, scoring progress, managing the
token budget, and redirecting the worker agent when it gets stuck — with no
human babysitting the screen.

> This npm package is the **TypeScript adapter / orchestration surface**. The
> Python core is published separately on PyPI as [`vexqr`](https://pypi.org/project/vexqr/).
> The security layer (scope enforcement, risk gating) is owned separately by the
> security team.

## Install

```bash
npm install -g vexqr      # or: pnpm add -g vexqr   |   bun add -g vexqr
```

The Python core:

```bash
pip install vexqr
```

## Usage

```bash
# Run a supervised assessment (simulated, safe — no tools installed/executed)
vexqr run "check if my web app is secure" --target scanme.nmap.org --dry-run

# Machine-readable JSON output
vexqr run "full security assessment" --target example.test --dry-run --json
```

Programmatic (TypeScript):

```ts
import { Orchestrator } from 'vexqr';

const orchestrator = new Orchestrator({ client: 'custom', dryRun: true });
const result = await orchestrator.run('check if my web app is secure', 'scanme.nmap.org');
console.log(result.summary);
```

## How it works

Five vertical layers plus a cross-cutting supervisor:

| Layer | Responsibility |
| ----- | -------------- |
| L1 adapters | Normalize any AI client into a task object; format results back. |
| L2 router | Classify and route each tool call (MCP first, terminal fallback). |
| L3 mcp | MCP registry, server lifecycle, trust-tier policy, transports. |
| L4 terminal | Auto-install cascade + PTY automation + output parser. |
| L5 supervisor | Loop detection, progress scoring, token budgets, feedback, escalation. |

## Development

```bash
npm install
npm run build      # tsc -> dist/
npm test           # node --test
```

## License

[MIT](./LICENSE) © ghulam
