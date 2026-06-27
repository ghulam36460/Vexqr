"""Configuration loading + validation.

User settings come from ``config.yaml`` (human-readable), validated against sane
defaults so a missing or partial file never crashes the platform.

The security layer (scope, risk gating, audit) is configured separately by the
security team and is intentionally absent here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from ..util.logger import get_logger

_log = get_logger("config")


@dataclass(slots=True)
class SupervisorConfig:
    loop_threshold: int = 3
    productivity_window: int = 5
    loop_escalation_limit: int = 3
    token_safety_margin: float = 0.15


@dataclass(slots=True)
class VexqrConfig:
    default_max_tokens: int = 200_000
    phase_budget: dict[str, float] = field(
        default_factory=lambda: {
            "recon": 0.15,
            "enumeration": 0.20,
            "vuln_scan": 0.25,
            "exploit": 0.20,
            "analysis": 0.05,
            "post_exploit": 0.05,
            "report": 0.10,
        }
    )
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    dry_run: bool = False
    registry_path: str = "config/registry.json"
    # When True, independent sub-tasks within a phase may dispatch in parallel
    # (offloaded to the Java performance layer when available).
    parallel_dispatch: bool = True
    max_parallelism: int = 8


DEFAULT_CONFIG = VexqrConfig()


def _coerce(base: VexqrConfig, raw: dict[str, Any]) -> VexqrConfig:
    sup = base.supervisor
    raw_sup = raw.get("supervisor") or {}
    sup = replace(
        sup,
        loop_threshold=int(raw_sup.get("loopThreshold", sup.loop_threshold)),
        productivity_window=int(raw_sup.get("productivityWindow", sup.productivity_window)),
        loop_escalation_limit=int(raw_sup.get("loopEscalationLimit", sup.loop_escalation_limit)),
        token_safety_margin=float(raw_sup.get("tokenSafetyMargin", sup.token_safety_margin)),
    )
    return replace(
        base,
        default_max_tokens=int(raw.get("defaultMaxTokens", base.default_max_tokens)),
        phase_budget={**base.phase_budget, **(raw.get("phaseBudget") or {})},
        supervisor=sup,
        dry_run=bool(raw.get("dryRun", base.dry_run)),
        registry_path=str(raw.get("registryPath", base.registry_path)),
        parallel_dispatch=bool(raw.get("parallelDispatch", base.parallel_dispatch)),
        max_parallelism=int(raw.get("maxParallelism", base.max_parallelism)),
    )


def load_config(path: str = "config/config.yaml") -> VexqrConfig:
    abs_path = Path(os.getcwd()) / path
    if not abs_path.exists():
        _log.warning("config not found at %s, using defaults", path)
        return DEFAULT_CONFIG
    try:
        import yaml  # local import so the core imports without PyYAML for typing

        raw = yaml.safe_load(abs_path.read_text("utf-8")) or {}
        cfg = _coerce(DEFAULT_CONFIG, raw)
        _validate(cfg)
        _log.info("loaded config from %s", path)
        return cfg
    except Exception as exc:  # pragma: no cover - defensive
        _log.error("failed to parse config, using defaults: %s", exc)
        return DEFAULT_CONFIG


def _validate(cfg: VexqrConfig) -> None:
    total = sum(cfg.phase_budget.values())
    if abs(total - 1.0) > 0.01:
        _log.warning("phaseBudget fractions sum to %.2f, expected ~1.0", total)
    if not 0.0 <= cfg.supervisor.token_safety_margin < 1.0:
        raise ValueError("supervisor.tokenSafetyMargin must be in [0, 1)")
