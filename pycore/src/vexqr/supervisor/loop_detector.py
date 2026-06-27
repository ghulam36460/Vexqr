"""Loop Detector (Supervisor sub-component 8.2.3).

Runs after every tool call. Computes a fuzzy signature of each
(tool, target, key-params) tuple and fires LOOP_DETECTED when K consecutive
recent calls are near-identical. Recon tools get a higher tolerance because
scanning is inherently iterative; exploit-class tools fire sooner.

Output is an ACTIONABLE redirect, not just "stop".
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.types import ToolCall
from ..util.ids import fnv1a
from .state import SubAgentState

_RECON_TOOLS = {"nmap", "subfinder", "amass", "shodan", "theharvester", "masscan"}
# Exploit-class tools loop sooner: repeated attempts are dangerous, not iterative.
_EXPLOIT_TOOLS = {"metasploit", "msfconsole", "sqlmap", "hydra", "medusa"}


@dataclass(slots=True)
class LoopVerdict:
    looping: bool
    repeated_count: int
    signature: str
    message: str | None = None


def _signature(call: ToolCall) -> str:
    tool = call.tool.lower()
    p = call.params
    host = str(p.get("host") or p.get("target") or "")
    ports = str(p.get("ports") or "")
    path = str(p.get("path") or p.get("url") or "")
    # Hash the fuzzy signature into a compact, fast-to-compare token via the
    # native (C/Assembly) FNV-1a fast path when present, pure-Python otherwise.
    return f"{tool}:{fnv1a(f'{tool}|{host}|{ports}|{path}'):016x}"


class LoopDetector:
    def __init__(self, base_threshold: int) -> None:
        self._base = base_threshold

    def check(self, state: SubAgentState, latest: ToolCall) -> LoopVerdict:
        sig = _signature(latest)
        tool = latest.tool.lower()
        if tool in _RECON_TOOLS:
            threshold = self._base + 2
        elif tool in _EXPLOIT_TOOLS:
            threshold = max(2, self._base - 1)
        else:
            threshold = self._base

        repeated = 0
        for call in reversed(state.tool_call_log):
            if _signature(call) == sig:
                repeated += 1
            else:
                break

        if repeated >= threshold:
            new_findings = "some" if state.calls_since_last_artifact == 0 else "0"
            host = latest.params.get("host") or latest.params.get("target")
            msg = (
                f"You have called '{tool}' on '{host}' {repeated} times with near-identical "
                f"parameters and found {new_findings} new findings in the last calls. "
                f"The information you need is not there. {self._suggest(state)}"
            )
            return LoopVerdict(True, repeated, sig, msg)
        return LoopVerdict(False, repeated, sig)

    def _suggest(self, state: SubAgentState) -> str:
        open_ports = [a.value for a in state.artifacts if a.kind == "port"]
        phase = state.current_phase
        if phase == "recon":
            if open_ports:
                return f"Move to enumeration: enumerate the open ports already found ({', '.join(open_ports)})."
            return "Switch discovery technique or target a different host/range instead of repeating this scan."
        if phase == "enumeration":
            return "Pivot to vulnerability scanning against the services you have already enumerated."
        if phase == "vuln_scan":
            return "Stop re-scanning. Triage the findings you have and decide whether any warrant exploitation."
        if phase == "exploit":
            return "Repeated exploit attempts are failing. Re-examine the target's actual version/config before retrying."
        return "Advance to the next phase using the findings already collected."
