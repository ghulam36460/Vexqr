# CLI Reference

Both cores ship a CLI. The Python command is `vexqr`; the TypeScript command is also
`vexqr` (via `dist/cli/index.js`).

## Python CLI (`vexqr`)

```
vexqr [-h] {run,registry,accel,history,export} ...
```

### `vexqr run`

Run a supervised assessment.

```
vexqr run [goal] [--target TARGET] [--dry-run] [--client CLIENT]
             [--yes|-y] [--demo-loop TOOL] [--verbose|-v]
             [--json] [--db DB] [--no-store]
```

| Flag | Description |
| ---- | ----------- |
| `goal` | Plain-English objective, e.g. `"check if my web app is secure"`. |
| `--target` | Target host / file, e.g. `scanme.nmap.org` or `myapp.exe`. |
| `--dry-run` | Simulate everything. No tools installed or executed. Always safe. |
| `--client` | AI client to adapt for: `claude`, `gemini`, `openai`, `custom`, … |
| `--yes`, `-y` | Skip interactive confirmations. |
| `--demo-loop TOOL` | Force `TOOL` to loop, to demonstrate supervisor loop detection. |
| `--verbose`, `-v` | Debug logging (shows MCP lifecycle, supervisor decisions). |
| `--json` | Print the result as machine-readable JSON. |
| `--db DB` | Session store path (default `.vexqr/sessions.db`). |
| `--no-store` | Do not persist this run. |

Examples:

```bash
vexqr run "check if my web app is secure" --target scanme.nmap.org --dry-run
vexqr run "help me debug this EXE binary, use Ghidra" --target myapp.exe --dry-run
vexqr run "full security assessment" --target scanme.nmap.org --dry-run --demo-loop nmap -v
vexqr run "full security assessment" --target example.test --dry-run --json
```

### `vexqr registry`

List the registered MCP tools.

### `vexqr accel`

Show native accelerator / Java performance-layer status, e.g.:

```
Native acceleration status:
  C/Assembly fast path : ENABLED
  Java perf layer      : not present (asyncio fallback)
```

### `vexqr history`

Show recent run history from the session store.

### `vexqr export`

Export run history (or a single run) as JSON:

```bash
vexqr export                 # all runs
vexqr export <task_id>       # one run
```

## TypeScript CLI

```bash
node dist/cli/index.js run "check if my web app is secure" --dry-run
npm run demo                    # preconfigured dry-run demo
npm run dev -- run "..." --dry-run   # run from source via tsx (no build)
```

The `run` subcommand accepts the same goal/`--dry-run` semantics as the Python CLI.
