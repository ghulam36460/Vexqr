# Sentinel Core (Python)

AI-Supervised Cybersecurity Tool Orchestration Platform — **Python core**.

A pipeline that connects any AI client (Claude, Gemini, Copilot, GitLab Duo,
Cursor, Codex, custom OpenAI-compatible) to security tools — via MCP servers
when available, or via terminal automation as a fallback — and supervises the
worker AI in real time so it does not loop, waste tokens, or wander.

The core is **Python**. It is supported by:

- **TypeScript** adapters for MCP / IDE clients (see the repository root).
- **C** and hand-tuned **Assembly** accelerators for hot paths (token
  estimation, fuzzy-signature hashing) — see `src/sentinel/accel`.
- A **Java 26** performance layer for high-throughput, cross-platform fan-out
  (parallel tool dispatch, concurrent sub-agent monitoring) — see
  `src/sentinel/perf`.

Everything degrades gracefully: with no native components installed the platform
runs in pure Python with identical behavior, just slower on the hot paths.

> The security layer (scope enforcement, risk gating, audit logging) is owned and
> implemented separately by the security team. It is intentionally **not** part of
> this package.

## Install

```bash
pip install .                 # pure-Python core (zero native build steps)
pip install '.[accel]'        # + C/Assembly fast paths and the Java bridge
pip install '.[mcp]'          # + official Model Context Protocol SDK
pip install '.[dev]'          # + test dependencies
```

### Optional: build the native accelerator

```bash
cd src/sentinel/accel && make            # C + hand-tuned x86-64 Assembly
# or, portable C only (any architecture):
cd src/sentinel/accel && make portable
```

### Optional: build the Java 26 performance layer

```bash
cd src/sentinel/perf
javac -d out java/com/sentinel/perf/DispatchCoordinator.java
jar --create --file sentinel-perf.jar -C out .
```

## Usage

```bash
# Run a supervised assessment (simulated, safe, no tools installed/executed)
sentinel run "check if my web app is secure" --target scanme.nmap.org --dry-run

# Emit machine-readable JSON
sentinel run "full security assessment" --target example.test --dry-run --json

# Inspect run history and export the audit trail
sentinel history
sentinel export <task_id>

# Registry + native acceleration status
sentinel registry
sentinel accel
```

Programmatic:

```python
import asyncio
from sentinel import Sentinel
from sentinel.platform import SentinelOptions
from sentinel.core.store import SessionStore

async def main():
    store = SessionStore()                       # persists to .sentinel/sessions.db
    sentinel = Sentinel(SentinelOptions(client="custom", dry_run=True, store=store))
    result = await sentinel.run("check if my web app is secure", "scanme.nmap.org")
    print(result.summary)

asyncio.run(main())
```

## Architecture

Five vertical layers plus a cross-cutting supervisor:

| Layer | Module | Responsibility |
| ----- | ------ | -------------- |
| L1 | `adapters/` | Normalize any AI client into a `TaskObject`; format results back. |
| L2 | `router/` | Classify + route each tool call (MCP first, terminal fallback). |
| L3 | `mcp/` | MCP registry, server lifecycle, trust-tier policy, transports. |
| L4 | `terminal/` | Auto-install cascade + PTY automation + output parser. |
| L5 | `supervisor/` | Loop detection, progress scoring, token budgets, feedback, escalation. |

Cross-cutting: `core/` (types, config, events, reporter, **SQLite session/audit
store**), `util/` (IDs, ANSI, logging, **native acceleration bridge**).

## Test

```bash
pip install '.[dev]'
pytest                # src/ is on the path via pyproject [tool.pytest.ini_options]
```
