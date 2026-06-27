"""Report generator — aggregates artifacts into a clear, prioritized summary.

Critical/high findings surface first so a non-technical user immediately sees
what matters. A lightweight risk score is computed from finding severities to
give an at-a-glance posture rating.
"""

from __future__ import annotations

import re

from .types import Artifact, Phase

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
_SEVERITY_WEIGHT = {"critical": 40, "high": 20, "medium": 8, "low": 3, "info": 1}


def _severity_of(a: Artifact) -> str:
    if a.detail:
        m = re.search(r"severity=(\w+)", a.detail, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    if a.kind in ("credential", "secret"):
        return "critical"
    if a.kind == "cve":
        return "high"
    if a.kind == "finding":
        return "medium"
    return "info"


def risk_score(artifacts: list[Artifact]) -> tuple[int, str]:
    """Return (numeric score 0-100, posture label)."""
    score = 0
    for a in artifacts:
        if a.kind in ("finding", "cve", "credential", "secret"):
            score += _SEVERITY_WEIGHT.get(_severity_of(a), 1)
    score = min(score, 100)
    if score >= 70:
        label = "CRITICAL"
    elif score >= 40:
        label = "HIGH"
    elif score >= 15:
        label = "MODERATE"
    elif score > 0:
        label = "LOW"
    else:
        label = "CLEAN"
    return score, label


def build_summary(artifacts: list[Artifact], phases_completed: list[Phase]) -> str:
    phases = " → ".join(phases_completed) if phases_completed else "none"
    if not artifacts:
        return f"Assessment complete. Phases run: {phases}. No findings were discovered."

    by_kind: dict[str, list[Artifact]] = {}
    for a in artifacts:
        by_kind.setdefault(a.kind, []).append(a)

    findings = sorted(
        (a for a in artifacts if a.kind in ("finding", "cve", "credential", "secret")),
        key=lambda x: _SEVERITY_ORDER.index(_severity_of(x))
        if _severity_of(x) in _SEVERITY_ORDER
        else len(_SEVERITY_ORDER),
    )

    score, label = risk_score(artifacts)
    lines: list[str] = []
    lines.append(f"Security assessment complete. Phases run: {phases}.")
    lines.append(f"Risk posture: {label} (score {score}/100).")
    lines.append("")
    lines.append("Attack surface discovered:")
    for kind, items in by_kind.items():
        if kind in ("finding", "cve", "credential", "secret"):
            continue
        sample = ", ".join(i.value for i in items[:8])
        plural = "s" if len(items) > 1 else ""
        lines.append(f"  - {len(items)} {kind}{plural}: {sample}")
    lines.append("")
    if findings:
        lines.append(f"Prioritized findings ({len(findings)}):")
        for f in findings[:20]:
            src = f" ({f.source})" if f.source else ""
            lines.append(f"  [{_severity_of(f).upper()}] {f.value}{src}")
    else:
        lines.append("No specific vulnerabilities were flagged. Surface mapping completed.")
    return "\n".join(lines)
