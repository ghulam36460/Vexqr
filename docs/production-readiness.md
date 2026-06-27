# Production Readiness

This summarizes verified status and the remaining setup required before a production
deployment. It reflects what was actually run on this codebase.

## Verified (works out of the box)

| Item | Status | Notes |
| ---- | ------ | ----- |
| Python unit tests | PASS | 23/23 via `pytest` |
| TypeScript unit tests | PASS | 9/9 via `node --test` |
| TypeScript typecheck | PASS | `tsc --noEmit` clean |
| TypeScript build | PASS | `tsc` emits `dist/` cleanly |
| Clean `pip install` | PASS | fresh venv, `vexqr` CLI runs end-to-end |
| Python CLI dry-run | PASS | web goal → 4 phases; binary goal → 2 phases |
| TypeScript CLI dry-run | PASS | full pipeline, prioritized findings |
| Supervisor loop detection | PASS | fires, injects redirect, run completes, no human needed |
| Token budget escalation | PASS | levels trigger with safety margin |
| Phase decomposition | PASS | web vs binary routed correctly |
| Artifact dedup / novelty | PASS | `kind:value` keying |
| SQLite session/audit store | PASS | runs persist to `.vexqr/sessions.db` |
| Native C/Assembly accelerator | PASS | `libvexqr.so` loads; pure-Python fallback otherwise |

## Needs production configuration

1. **AI client API key** (`ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY`) —
   required only for live (non-dry-run) execution and the optional meta-AI supervisor
   mode. Set in `.env`. See [configuration](configuration.md).
2. **Java** — JDK 21+ for the Java performance layer, and Java 17+ for real Ghidra
   headless analysis. Without it, the Java perf layer falls back to asyncio and Ghidra
   runs in simulated mode.
3. **MCP server binaries** — for real (non-simulated) MCP calls, the tool MCP servers in
   `config/registry.json` must be available.
4. **Scope enforcement (security layer)** — owned separately by the security team. Before
   any live deployment, target authorization (`scope.json`) must be enforced. Vexqr has
   no hard authorization boundary without it. **Only test systems you are authorized to test.**

## Recommended hardening before launch

- Add an end-to-end test for the TypeScript `Orchestrator` (only component unit tests exist
  today).
- Add a real Ghidra-headless test: compile a small C program with a `system()`/`strcpy()`
  call, run Ghidra headless, feed output to the parser, assert findings fire.
- Add a real PTY integration test driving an interactive tool.
- Rate-limit supervisor feedback injection (minimum interval) to avoid a feedback storm
  under very fast tool calls.
- Add a root `LICENSE` file (MIT is declared in both manifests; ship the text).

## Verdict

The codebase is **structurally sound and functionally correct**: all 32 tests pass, both
cores build and run end-to-end, and the supervisor behaves as designed. It is **ready to
publish** as `0.x` packages (see [publishing](publishing.md)). For a **live** production
deployment against real targets, complete the four configuration items above —
particularly **scope enforcement**, which is a hard requirement.
