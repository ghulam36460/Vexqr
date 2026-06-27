"""Task Decomposer & Execution Planner (Supervisor sub-component 8.2.1).

Breaks a high-level user request into a phase-ordered plan. Each node carries a
tool whitelist, a token-budget slice and a sub-agent profile. Phase selection is
inferred from the natural-language goal so a non-technical user never has to name
a phase or a tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.config import SentinelConfig
from ..core.types import Phase, TaskObject

PHASE_TOOLS: dict[Phase, list[str]] = {
    "recon": ["nmap", "masscan", "subfinder", "amass", "shodan", "theharvester"],
    "enumeration": ["gobuster", "ffuf", "feroxbuster", "enum4linux", "smbclient", "ldapsearch", "whatweb", "httpx"],
    "vuln_scan": ["nuclei", "nikto", "openvas", "wpscan", "sslscan", "testssl", "trivy"],
    "exploit": ["metasploit", "sqlmap", "hydra", "medusa"],
    "analysis": ["ghidra", "radare2", "binwalk", "yara", "strings"],
    "post_exploit": ["volatility", "cyberchef", "linpeas"],
    "report": [],
}

PHASE_PROFILES: dict[Phase, str] = {
    "recon": "Recon specialist: map the attack surface using passive and active discovery. Do not exploit.",
    "enumeration": "Enumeration specialist: enumerate services and content on discovered hosts. Do not exploit.",
    "vuln_scan": "Vulnerability analyst: identify and triage weaknesses. Do not exploit without authorization.",
    "exploit": "Exploitation specialist: validate vulnerabilities. Every action requires a human gate.",
    "analysis": "Reverse engineering / analysis specialist for binaries and artifacts.",
    "post_exploit": "Post-exploitation analyst: analyze collected data. Sequential, careful operations.",
    "report": "Reporting agent: aggregate all findings into a clear, prioritized report.",
}


@dataclass(slots=True)
class PlanNode:
    phase: Phase
    tool_whitelist: list[str]
    token_budget: int
    profile: str
    requires_human_gate: bool


def infer_phases(text: str) -> list[Phase]:
    t = text.lower()
    if re.search(r"(reverse engineer|\bexe\b|binary|ghidra|decompile|malware|debug|firmware)", t):
        return ["analysis", "report"]
    if re.search(r"(exploit|gain access|pop a shell|break in|foothold)", t):
        return ["recon", "enumeration", "vuln_scan", "exploit", "report"]
    if re.search(r"(full|complete|thorough|pentest|penetration|assessment|audit)", t):
        return ["recon", "enumeration", "vuln_scan", "report"]
    if re.search(r"(secure|vulnerab|owasp|sql injection|xss|safe|check.*app|web app)", t):
        return ["recon", "enumeration", "vuln_scan", "report"]
    return ["recon", "vuln_scan", "report"]


class TaskDecomposer:
    def __init__(self, config: SentinelConfig) -> None:
        self._config = config

    def plan(self, task: TaskObject) -> list[PlanNode]:
        phases = infer_phases(task.natural_input)
        total = task.constraints.max_tokens
        fractions = [self._config.phase_budget.get(p, 0.1) for p in phases]
        frac_sum = sum(fractions) or 1.0
        return [
            PlanNode(
                phase=phase,
                tool_whitelist=PHASE_TOOLS[phase],
                token_budget=int((fractions[i] / frac_sum) * total),
                profile=PHASE_PROFILES[phase],
                requires_human_gate=(phase == "exploit"),
            )
            for i, phase in enumerate(phases)
        ]

    def reallocate(self, nodes: list[PlanNode], from_index: int, surface_multiplier: float) -> None:
        if surface_multiplier <= 1:
            return
        for i in range(from_index + 1, len(nodes)):
            nodes[i].token_budget = int(nodes[i].token_budget * min(surface_multiplier, 3))
