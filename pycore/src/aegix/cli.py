"""Aegix CLI — reference host application.

Usage:
  aegix run "<goal>" --target <host> [--dry-run] [--client <id>]
                        [--yes] [--demo-loop <tool>] [--verbose]
  aegix registry
  aegix accel        Show native accelerator / Java performance layer status
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import json as _json

from .core.config import load_config
from .core.events import bus
from .core.store import SessionStore
from .mcp.registry import McpRegistry
from .platform import Aegix, AegixOptions
from .supervisor.escalation import EscalationRequest
from .util.accel import accel
from .util.logger import set_log_level

_DEFAULT_DB = ".aegix/sessions.db"


def _wire_live_log(stream=sys.stdout) -> None:
    """Stream live progress events.

    When the caller requests machine-readable output (``--json``), the live log
    is routed to ``stderr`` so that ``stdout`` carries only the JSON document and
    stays parseable by downstream consumers.
    """

    def out(msg: str) -> None:
        print(msg, file=stream)

    bus.on("phase:enter", lambda e: out(f"\n=== PHASE: {e['phase'].upper()} ==="))
    bus.on("tool:call", lambda c: out(f"  → {c.tool} {c.params}"))
    bus.on("artifact:new", lambda e: out(f"    + {e['artifact'].kind}: {e['artifact'].value}"))
    bus.on("supervisor:feedback", lambda f: out(f"  ⚠ SUPERVISOR [{f['reason']}]: {f['message']}"))
    bus.on("supervisor:escalate", lambda e: out(f"  ⛔ ESCALATION [{e['reason']}]: {e['summary']}"))

    def _budget(b: dict) -> None:
        if b["level"] not in ("monitor", "watch"):
            out(f"  $ budget {b['level']}: {b['tokensUsed']}/{b['tokensBudget']} tokens")

    bus.on("budget:level", _budget)


def _prompt(question: str) -> bool:
    try:
        return input(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


async def _cmd_run(args: argparse.Namespace) -> None:
    if not args.goal:
        print('error: provide a goal, e.g. aegix run "check if my web app is secure" --target example.test')
        sys.exit(1)
    if args.verbose:
        set_log_level("debug")
    # In --json mode, keep stdout clean for the JSON document: send all
    # human-readable progress to stderr instead.
    log_stream = sys.stderr if args.json else sys.stdout
    _wire_live_log(log_stream)

    auto_yes = args.yes

    async def confirm_mcp(prompt: str) -> bool:
        return True if auto_yes else _prompt(prompt)

    async def human_gate(req: EscalationRequest):
        print(f"\n  ⛔ HUMAN GATE [{req.reason}]: {req.summary}")
        if auto_yes:
            return "deny"
        return "approve" if _prompt("     Approve? [y/N] ") else "deny"

    store = None if args.no_store else SessionStore(args.db)

    app = Aegix(
        AegixOptions(
            client=args.client,
            dry_run=args.dry_run,
            simulate_loop_on=args.demo_loop,
            confirm_mcp=confirm_mcp,
            human_gate=human_gate,
            store=store,
        )
    )

    mode = "DRY-RUN (simulated)" if args.dry_run else "LIVE"
    banner_stream = sys.stderr if args.json else sys.stdout
    print(f'\nGoal: "{args.goal}"\nTarget: {args.target}\nMode: {mode}', file=banner_stream)
    result = await app.run(args.goal, args.target)

    if args.json:
        print(_json.dumps(result.to_native(), indent=2))
    else:
        print("\n" + "=" * 60 + f"\nRESULT ({result.status})\n" + "=" * 60)
        print(result.summary + "\n")
        print(f"Tokens used: {result.tokens_used} / {result.tokens_budget}")
        print(f"Phases: {' → '.join(result.phases_completed)}")
        if store is not None:
            print(f"\nSession saved to {args.db} (task {result.task_id[:8]}…)")

    if store is not None:
        store.close()


def _cmd_history(args: argparse.Namespace) -> None:
    store = SessionStore(args.db)
    runs = store.recent_runs(args.limit)
    store.close()
    if not runs:
        print("No runs recorded yet.")
        return
    print(f"Recent runs ({len(runs)}):")
    for r in runs:
        print(
            f"  {r['task_id'][:8]}  {r['status']:9}  risk={r['risk_label']:8} "
            f"({r['risk_score']:>3}/100)  {r['client']:10}  {r['goal'][:42]}"
        )


def _cmd_export(args: argparse.Namespace) -> None:
    store = SessionStore(args.db)
    if args.task_id:
        print(_json.dumps(store.run_detail(args.task_id), indent=2, default=str))
    else:
        print(store.to_json())
    store.close()


def _cmd_registry(_args: argparse.Namespace) -> None:
    cfg = load_config()
    reg = McpRegistry.load(cfg.registry_path)
    print("Registered MCP tools:")
    for name in reg.list():
        e = reg.get(name)
        assert e is not None
        print(f"  - {name} [{e.trust_tier}] {e.transport} {e.mcp_server}")


def _cmd_accel(_args: argparse.Namespace) -> None:
    print("Native acceleration status:")
    print(f"  C/Assembly fast path : {'ENABLED' if accel.has_native else 'not present (pure-Python fallback)'}")
    print(f"  Java perf layer      : {'available' if accel.jvm_available() else 'not present (asyncio fallback)'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="aegix", description="AI-Supervised Cybersecurity Tool Orchestration")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run a supervised assessment")
    run.add_argument("goal", nargs="?")
    run.add_argument("--target", default="scanme.nmap.org")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--client", default="custom")
    run.add_argument("--yes", "-y", action="store_true")
    run.add_argument("--demo-loop", default=None)
    run.add_argument("--verbose", "-v", action="store_true")
    run.add_argument("--json", action="store_true", help="Print the result as JSON")
    run.add_argument("--db", default=_DEFAULT_DB, help="Session store path")
    run.add_argument("--no-store", action="store_true", help="Do not persist this run")

    sub.add_parser("registry", help="List registered MCP tools")
    sub.add_parser("accel", help="Show native accelerator / Java performance layer status")

    hist = sub.add_parser("history", help="Show recent run history")
    hist.add_argument("--db", default=_DEFAULT_DB)
    hist.add_argument("--limit", type=int, default=20)

    exp = sub.add_parser("export", help="Export run history (or one run) as JSON")
    exp.add_argument("task_id", nargs="?", default=None)
    exp.add_argument("--db", default=_DEFAULT_DB)

    args = parser.parse_args(argv)
    if args.command == "run":
        asyncio.run(_cmd_run(args))
    elif args.command == "registry":
        _cmd_registry(args)
    elif args.command == "accel":
        _cmd_accel(args)
    elif args.command == "history":
        _cmd_history(args)
    elif args.command == "export":
        _cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
