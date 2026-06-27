# Getting Started

Vexqr has two cores. You can use either independently; most users start with the
Python core.

## Requirements

- **Python** >= 3.12 (for `vexqr-core`)
- **Node.js** >= 20 (for `vexqr-orchestrator`)
- Optional: a C toolchain and `make` (native accelerator), JDK 21+ (Java perf layer), Java 17+ (real Ghidra)

## 1. Python core (`pip`)

```bash
cd pycore
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install .                      # pure-Python core, no native build steps
# optional extras:
pip install '.[mcp]'               # official Model Context Protocol SDK
pip install '.[accel]'             # C/Assembly fast paths + Java bridge
pip install '.[dev]'               # test dependencies
```

Verify:

```bash
vexqr --help
vexqr run "check if my web app is secure" --target scanme.nmap.org --dry-run
```

Expected: a 4-phase run (`recon → enumeration → vuln_scan → report`) with prioritized
findings and a token count. `--dry-run` installs and executes **nothing**; all tool
output is simulated, so it is always safe.

## 2. TypeScript adapter (`npm` / `bun`)

```bash
# from the repository root
npm install        # or: bun install
npm run build      # compiles src/ -> dist/ via tsc
npm run demo       # dry-run end-to-end demo
```

Run the CLI directly:

```bash
node dist/cli/index.js run "check if my web app is secure" --dry-run
# during development, without building:
npm run dev -- run "check if my web app is secure" --dry-run
```

## 3. Connect an AI client

Vexqr talks to whichever AI client you already use. Credentials are read from the
environment. Copy the example and fill in only the keys you need:

```bash
cp config/.env.example .env
# then edit .env:
#   ANTHROPIC_API_KEY=...        # Claude (supervisor "ai" mode + LLM fallback parser)
#   GEMINI_API_KEY=...
#   OPENAI_API_KEY=...           # any OpenAI-compatible endpoint
#   OPENAI_API_BASE=https://api.openai.com/v1
#   VEXQR_LOG_LEVEL=info
```

Without any key, Vexqr still runs fully in `--dry-run` / heuristic mode. Keys are only
required for live MCP/terminal execution and the optional meta-AI supervisor mode.

## 4. Run the tests

```bash
# Python
cd pycore && source .venv/bin/activate && pip install '.[dev]' && pytest

# TypeScript (from repo root)
npm install && npm test
```

## Programmatic use (Python)

```python
import asyncio
from vexqr import Vexqr
from vexqr.platform import VexqrOptions
from vexqr.core.store import SessionStore

async def main():
    store = SessionStore()  # persists an audit trail to .vexqr/sessions.db
    app = Vexqr(VexqrOptions(client="custom", dry_run=True, store=store))
    result = await app.run("check if my web app is secure", "scanme.nmap.org")
    print(result.summary)

asyncio.run(main())
```
