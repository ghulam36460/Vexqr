"""Layer 4 — Output Parser.

Two-pass parsing of messy terminal output into structured Artifacts:
  Pass 1 — Known Format Library: regex/format parsers for common tools.
  Pass 2 — Generic extraction (CVEs, IPs, emails, secrets) standing in for the
           small-model "LLM fallback" parser described in the architecture.

The parsed artifacts feed the supervisor's progress scorer and the final report.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from ..core.types import Artifact
from ..util.ansi import strip_ansi

ParserFn = Callable[[str], list[Artifact]]

_NMAP_PORT = re.compile(r"^(\d{1,5})/tcp\s+open\s+(\S+)(?:\s+(.*))?$")
_GOBUSTER = re.compile(r"^(/\S+)\s+\(Status:\s*(\d{3})\)")
_NUCLEI_SEV = re.compile(r'"severity"\s*:\s*"(\w+)"')
_NUCLEI_TPL = re.compile(r'"template-id"\s*:\s*"([^"]+)"')
_CVE = re.compile(r"CVE-\d{4}-\d{4,7}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SECRET = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.)"
)
_DOMAIN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)


def _parse_nmap(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        m = _NMAP_PORT.match(line.strip())
        if m:
            out.append(Artifact("port", m.group(1), "nmap", f"{m.group(2)} {m.group(3) or ''}".strip()))
            out.append(Artifact("service", m.group(2), "nmap", f"port {m.group(1)}"))
    for ip in _IPV4.findall(text):
        out.append(Artifact("host", ip, "nmap"))
    return out


def _parse_gobuster(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        m = _GOBUSTER.match(line.strip())
        if m:
            out.append(Artifact("path", m.group(1), "gobuster", f"status {m.group(2)}"))
    return out


def _parse_nuclei(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        tpl = _NUCLEI_TPL.search(line)
        if not tpl:
            try:
                obj = json.loads(line)
                tpl_id = obj.get("template-id")
                sev = (obj.get("info") or {}).get("severity", "info")
            except Exception:
                continue
        else:
            tpl_id = tpl.group(1)
            sev_m = _NUCLEI_SEV.search(line)
            sev = sev_m.group(1) if sev_m else "info"
        if tpl_id:
            out.append(Artifact("finding", tpl_id, "nuclei", f"severity={sev}"))
    return out


def _parse_nikto(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        t = line.strip()
        if t.startswith("+") and len(t) > 3:
            out.append(Artifact("finding", re.sub(r"^\+\s*", "", t), "nikto"))
    return out


def _parse_subfinder(text: str) -> list[Artifact]:
    return [
        Artifact("domain", line.strip(), "subfinder")
        for line in text.splitlines()
        if _DOMAIN.match(line.strip())
    ]


def _parse_ghidra(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        t = line.strip()
        if re.search(r"suspicious|system\(|/bin/sh|string reference|strcpy|gets\(", t, re.IGNORECASE):
            out.append(Artifact("finding", t, "ghidra"))
    return out


def _parse_whatweb(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for m in re.finditer(r"\b([A-Z][A-Za-z]+)(?:\[([^\]]+)\])?", text):
        name = m.group(1)
        if name in {"GET", "POST", "HTTP"}:
            continue
        ver = m.group(2)
        out.append(Artifact("tech", f"{name}{('/' + ver) if ver else ''}", "whatweb"))
    return out


def _parse_httpx(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        url = obj.get("url")
        if url:
            sc = obj.get("status_code")
            out.append(Artifact("path", url, "httpx", f"status {sc}" if sc else None))
        for t in obj.get("tech", []) or []:
            out.append(Artifact("tech", str(t), "httpx"))
    return out


def _parse_trivy(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        vid = obj.get("VulnerabilityID")
        if vid:
            sev = str(obj.get("Severity", "info")).lower()
            pkg = obj.get("PkgName", "")
            out.append(Artifact("cve", vid, "trivy", f"severity={sev} pkg={pkg}"))
    return out


def _parse_sslscan(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        t = line.strip()
        low = t.lower()
        if "vulnerable" in low or "heartbleed" in low:
            sev = "critical" if "heartbleed" in low or "cve" in low else "high"
            out.append(Artifact("finding", t, "sslscan", f"severity={sev}"))
        elif "certificate expired: yes" in low:
            out.append(Artifact("finding", "TLS certificate expired", "sslscan", "severity=medium"))
    return out


def _parse_wpscan(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    for line in text.splitlines():
        t = line.strip()
        if t.startswith("[!]"):
            sev = "high" if "vulnerab" in t.lower() or "cve" in t.lower() else "medium"
            out.append(Artifact("finding", re.sub(r"^\[!\]\s*", "", t), "wpscan", f"severity={sev}"))
    return out


def _parse_sqlmap(text: str) -> list[Artifact]:
    out: list[Artifact] = []
    if re.search(r"Type:\s+\w+", text) or "is vulnerable" in text.lower():
        out.append(Artifact("finding", "SQL injection confirmed", "sqlmap", "severity=critical"))
    m = re.search(r"available databases.*?:\s*(.+)", text)
    if m:
        for db in re.split(r"[,\s]+", m.group(1).strip()):
            if db:
                out.append(Artifact("path", f"db:{db}", "sqlmap"))
    return out


_KNOWN: dict[str, ParserFn] = {
    "nmap": _parse_nmap,
    "masscan": _parse_nmap,
    "gobuster": _parse_gobuster,
    "ffuf": _parse_gobuster,
    "feroxbuster": _parse_gobuster,
    "nuclei": _parse_nuclei,
    "nikto": _parse_nikto,
    "subfinder": _parse_subfinder,
    "amass": _parse_subfinder,
    "ghidra": _parse_ghidra,
    "whatweb": _parse_whatweb,
    "httpx": _parse_httpx,
    "trivy": _parse_trivy,
    "sslscan": _parse_sslscan,
    "testssl": _parse_sslscan,
    "wpscan": _parse_wpscan,
    "sqlmap": _parse_sqlmap,
}


def _generic(text: str, tool: str) -> list[Artifact]:
    out: list[Artifact] = []
    for cve in _CVE.findall(text):
        out.append(Artifact("cve", cve, tool))
    for ip in _IPV4.findall(text):
        out.append(Artifact("host", ip, tool))
    for email in _EMAIL.findall(text):
        out.append(Artifact("email", email, tool))
    for secret in _SECRET.findall(text):
        out.append(Artifact("secret", secret[:24] + "…", tool, "possible leaked credential"))
    return out


def _dedup(items: list[Artifact]) -> list[Artifact]:
    seen: set[str] = set()
    out: list[Artifact] = []
    for a in items:
        if a.key not in seen:
            seen.add(a.key)
            out.append(a)
    return out


def parse_tool_output(tool: str, raw: str) -> list[Artifact]:
    text = strip_ansi(raw)
    parser = _KNOWN.get(tool.lower())
    if parser:
        artifacts = parser(text)
        if artifacts:
            # Always also run generic extraction so secrets/CVEs in any tool surface.
            return _dedup(artifacts + _generic(text, tool))
    return _dedup(_generic(text, tool))
