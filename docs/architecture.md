# Architecture

Vexqr is organized as five vertical layers plus a cross-cutting **AI Supervisor**. The
Python core (`pycore/src/vexqr`) and the TypeScript adapter (`src/`) mirror the same
structure so behavior is consistent across both.

## The five layers

| Layer | Python module | TypeScript module | Responsibility |
| ----- | ------------- | ----------------- | -------------- |
| L1 Adapters | `adapters/` | `adapters/` | Normalize any AI client into a `TaskObject`; format results back to the client. |
| L2 Router | `router/` | `router/` | Classify each tool call and route it: **MCP first**, terminal fallback. |
| L3 MCP | `mcp/` | `mcp/` | MCP registry, server lifecycle, trust-tier policy, stdio/transport handling. |
| L4 Terminal | `terminal/` | `terminal/` | Auto-install cascade (OS detection + package manager), PTY automation, output parser. |
| L5 Supervisor | `supervisor/` | `supervisor/` | Loop detection, progress scoring, token budgets, feedback injection, escalation. |

Cross-cutting:

- `core/` — types, config loader, event bus, reporter, and the **SQLite session/audit store**.
- `util/` — IDs, ANSI, logging, and the **native acceleration bridge** (C/Assembly, Java).

## Request flow

1. **Adapter (L1)** turns a plain-English goal (`"check if my web app is secure"`) plus a
   target into a `TaskObject`.
2. **Decomposer (L5)** infers the phases the goal needs. A web goal becomes
   `recon → enumeration → vuln_scan → report`; a binary/EXE goal becomes
   `analysis → report` (recon/enum/vuln_scan are skipped as irrelevant).
3. For each phase, the **Router (L2)** picks a tool and decides MCP vs terminal.
4. **MCP engine (L3)** calls the tool over an MCP server when one is registered; otherwise
   the **Terminal engine (L4)** installs the tool and drives it in a PTY.
5. Raw output is parsed into typed **artifacts** (`port`, `service`, `host`, `path`,
   `finding`, …) and **deduplicated** by a `kind:value` key.
6. The **Supervisor (L5)** watches every call in real time (see below).
7. The **Reporter (`core/`)** prioritizes findings by severity and produces the summary;
   the run is persisted to `.vexqr/sessions.db`.

## The AI Supervisor (L5)

Runs alongside the worker AI and intervenes without a human:

- **Loop detection** — if a tool is called repeatedly with near-identical parameters and
  produces no novel artifacts, the supervisor fires `LOOP_DETECTED`, injects a redirect
  (e.g. "move to enumeration of the ports already found"), and the worker advances. Recon
  tools get a more tolerant threshold; exploit tools fire sooner.
- **Progress scoring** — flags low productivity after a configurable window of calls with
  no new findings.
- **Token budget** — escalates through levels (`monitor → watch → warn → critical →
  force_wrap → exhausted`) with a configurable safety margin, telling the worker to
  prioritize, summarize, or stop as the budget is consumed.
- **Feedback injection** — delivers actionable steering messages as system messages.
- **Escalation** — after repeated loops on a single task, escalates to a human.

## Native acceleration (optional)

Hot paths (token estimation, fuzzy-signature hashing) have **C + hand-tuned x86-64
Assembly** fast paths in `pycore/src/vexqr/accel`, and a **Java** performance layer in
`pycore/src/vexqr/perf` for high-throughput parallel dispatch. Both are optional:
with nothing built, the platform runs in pure Python with identical behavior, just slower
on those paths. At startup the CLI reports which accelerators loaded (`vexqr accel`).
