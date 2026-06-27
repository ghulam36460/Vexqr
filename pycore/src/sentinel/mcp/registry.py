"""Layer 3 — MCP Registry.

The "smart phone book" of security-tool MCP servers. Maps a tool name to its MCP
server image, transport, install method and trust tier. The router queries this
first; only tools NOT found here fall through to terminal automation (L4).

Whitelist-only: a tool not present in the registry is never auto-executed via
MCP — it is blocked or handled by L4, never silently trusted.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..util.logger import get_logger

_log = get_logger("mcp-registry")

Transport = Literal["stdio", "sse", "http"]
TrustTier = Literal["official", "community", "experimental"]


@dataclass(slots=True)
class RegistryEntry:
    mcp_server: str
    transport: Transport
    trust_tier: TrustTier
    install: dict[str, str] = field(default_factory=dict)
    sha256: str | None = None
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)


SEED_TOOLS: dict[str, RegistryEntry] = {
    "nuclei": RegistryEntry("ghcr.io/projectdiscovery/nuclei-mcp:latest", "stdio", "official", {"native": "pip install nuclei-cli"}),
    "ghidra": RegistryEntry("github:bethington/ghidra-mcp@v2.1", "stdio", "community"),
    "nmap": RegistryEntry("ghcr.io/org/nmap-mcp:latest", "stdio", "community", {"native": "apt install nmap"}),
    "semgrep": RegistryEntry("ghcr.io/semgrep/semgrep-mcp:latest", "stdio", "official", {"native": "pip install semgrep"}),
}


class McpRegistry:
    def __init__(self, tools: dict[str, RegistryEntry] | None = None) -> None:
        self._tools = tools if tools is not None else dict(SEED_TOOLS)

    @staticmethod
    def normalize(tool: str) -> str:
        return re.sub(r"[@:].*$", "", tool.lower()).strip()

    @classmethod
    def load(cls, path: str) -> "McpRegistry":
        abs_path = Path(os.getcwd()) / path
        if not abs_path.exists():
            _log.warning("registry not found at %s, using seed manifest", path)
            return cls()
        try:
            manifest = json.loads(abs_path.read_text("utf-8"))
            tools: dict[str, RegistryEntry] = {}
            for name, e in (manifest.get("tools") or {}).items():
                tools[cls.normalize(name)] = RegistryEntry(
                    mcp_server=e.get("mcpServer", ""),
                    transport=e.get("transport", "stdio"),
                    trust_tier=e.get("trustTier", "community"),
                    install=e.get("install", {}) or {},
                    sha256=e.get("sha256"),
                    tool_schemas=e.get("toolSchemas", []) or [],
                )
            _log.info("loaded registry (%d tools)", len(tools))
            return cls(tools)
        except Exception as exc:  # pragma: no cover - defensive
            _log.error("failed to parse registry, using seed: %s", exc)
            return cls()

    def has(self, tool: str) -> bool:
        return self.normalize(tool) in self._tools

    def get(self, tool: str) -> RegistryEntry | None:
        return self._tools.get(self.normalize(tool))

    def list(self) -> list[str]:
        return sorted(self._tools.keys())
