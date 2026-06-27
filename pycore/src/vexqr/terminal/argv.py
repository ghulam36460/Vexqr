"""Translate structured tool params into a safe argv list for a CLI tool.

Using an explicit argv (no shell) avoids shell injection. Each known tool has a
small mapper; unknown tools get a generic flag-mapping fallback.
"""

from __future__ import annotations

from typing import Any, Callable

ArgvFn = Callable[[dict[str, Any]], list[str]]


def _s(v: Any, fallback: str = "") -> str:
    return fallback if v is None else str(v)


def _nmap(p: dict[str, Any]) -> list[str]:
    args = ["-Pn"]
    if p.get("serviceDetection") is not False:
        args.append("-sV")
    if p.get("ports"):
        args += ["-p", _s(p["ports"])]
    args.append(_s(p.get("host") or p.get("target")))
    return args


_MAPPERS: dict[str, ArgvFn] = {
    "nmap": _nmap,
    "gobuster": lambda p: ["dir", "-u", _s(p.get("host") or p.get("url")), "-w", _s(p.get("wordlist"), "/usr/share/wordlists/dirb/common.txt")],
    "nuclei": lambda p: ["-u", _s(p.get("host") or p.get("url")), "-jsonl"],
    "nikto": lambda p: ["-h", _s(p.get("host") or p.get("url"))],
    "subfinder": lambda p: ["-d", _s(p.get("host") or p.get("domain")), "-silent"],
    "whatweb": lambda p: [_s(p.get("host") or p.get("url"))],
    "httpx": lambda p: ["-u", _s(p.get("host") or p.get("url")), "-json", "-silent"],
    "trivy": lambda p: ["image", "--format", "json", _s(p.get("image") or p.get("host") or p.get("target"))],
    "sslscan": lambda p: [_s(p.get("host") or p.get("target"))],
    "testssl": lambda p: ["--quiet", _s(p.get("host") or p.get("url"))],
    "wpscan": lambda p: ["--url", _s(p.get("host") or p.get("url")), "--no-banner"],
    "sqlmap": lambda p: ["-u", _s(p.get("host") or p.get("url")), "--batch"],
}


def build_argv(tool: str, params: dict[str, Any]) -> list[str]:
    mapper = _MAPPERS.get(tool.lower())
    if mapper:
        return mapper(params)
    args: list[str] = []
    for k, v in params.items():
        if k in ("host", "target", "timeoutMs", "timeout_ms"):
            continue
        if v is True:
            args.append(f"--{k}")
        elif v not in (False, None):
            args += [f"--{k}", str(v)]
    target = params.get("target") or params.get("host")
    if target is not None:
        args.append(str(target))
    return args
