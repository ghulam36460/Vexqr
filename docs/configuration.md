# Configuration

Aegix reads configuration from three places, all optional. Anything omitted falls back
to built-in defaults.

1. `config/config.yaml` — platform behavior and supervisor tuning.
2. `config/registry.json` — the MCP tool registry.
3. Environment variables (`.env`) — AI client credentials and logging.

## `config/config.yaml`

```yaml
defaultMaxTokens: 200000

# Fraction of the total token budget per phase (re-normalized across the phases
# actually selected for a goal). Should sum to ~1.0.
phaseBudget:
  recon: 0.15
  enumeration: 0.20
  vuln_scan: 0.25
  exploit: 0.20
  analysis: 0.05
  post_exploit: 0.05
  report: 0.10

supervisor:
  loopThreshold: 3          # consecutive near-identical calls before a loop fires
  productivityWindow: 5     # calls without a new finding before low-productivity fires
  loopEscalationLimit: 3    # loops on one task before escalating to a human
  tokenSafetyMargin: 0.15   # reserve 15% of the budget as headroom

dryRun: false               # when true, nothing is installed or executed; output simulated

registryPath: config/registry.json
```

> The security layer (scope enforcement, risk gating, audit logging) is configured
> separately by the security team and is intentionally not defined here.

## `config/registry.json`

The MCP tool registry maps tool names to their MCP server image/transport and trust tier.
Official tools auto-run; community/experimental tools prompt before running. List the
active registry at any time with `aegix registry`.

## Environment variables (`.env`)

Copy `config/.env.example` to `.env` and fill in only what you use:

```bash
ANTHROPIC_API_KEY=        # Claude: supervisor "ai" mode + LLM fallback parser
GEMINI_API_KEY=
OPENAI_API_KEY=           # any OpenAI-compatible model
OPENAI_API_BASE=https://api.openai.com/v1
AEGIX_LOG_LEVEL=info   # debug | info | warn | error
```

`.env` is git-ignored; only `.env.example` is committed.

## Enabling the meta-AI supervisor (production)

To use a live model as the supervisor and as the fallback parser for unknown tool output:

```yaml
# config/config.yaml
supervisor:
  mode: "ai"
  model: "claude-haiku-4-5"     # a small, fast model is sufficient

output_parser:
  llm_fallback: true
  model: "claude-haiku-4-5"
```

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Without a key, the supervisor runs in heuristic mode (loop/progress/token rules only),
which is fully functional and is what the test suite exercises.
