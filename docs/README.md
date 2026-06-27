# Aegix Documentation

Aegix is an **AI-Supervised Cybersecurity Tool Orchestration Platform**. It connects any
AI client (Claude, Gemini, Copilot, GitLab Duo, Cursor, Codex, or a custom
OpenAI-compatible model) to security tools — through **MCP servers** when available, or
through **PTY terminal automation** as a fallback — and runs a real-time **AI Supervisor**
that keeps the worker AI from looping, wasting tokens, or wandering.

**Version 2.0.0.** The platform ships as two coordinated packages:

| Package | Path | Language | Distribution |
| ------- | ---- | -------- | ------------ |
| `aegix-core` 2.0.0 | `pycore/` | Python (core) | **pip** |
| `aegix-orchestrator` 2.0.0 | repo root | TypeScript (adapter/CLI) | **npm / bun** |

> The security layer (scope enforcement, risk gating, authorization) is owned and
> implemented separately by the security team and is intentionally not part of these
> packages. **Only run Aegix against systems you are explicitly authorized to test.**

## Documentation index

- [Getting Started](getting-started.md) — install, first run, both cores.
- [Architecture](architecture.md) — the five layers and the supervisor.
- [CLI Reference](cli-reference.md) — every command and flag.
- [Configuration](configuration.md) — `config.yaml`, registry, environment variables.
- [Publishing](publishing.md) — how to publish to **pip** and **bun/npm**.
- [Production Readiness](production-readiness.md) — checklist and what needs setup.

## Verified status

Both test suites pass and both cores run end-to-end:

- Python core: **23/23** tests pass (`pytest`).
- TypeScript adapter: **9/9** tests pass (`node --test`).
- `tsc` typecheck and build: clean.
- Clean `pip install` into a fresh virtualenv: succeeds, `aegix` CLI runs.
- Supervisor loop detection: fires, injects a redirect, run completes with no human in the loop.
