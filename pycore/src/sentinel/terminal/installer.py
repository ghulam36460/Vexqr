"""Layer 4 — Auto-Installer Cascade.

When a tool is required but missing, try installation methods in order until one
succeeds: apt -> pip -> cargo -> go -> npm -> brew -> winget -> git+make -> docker.
On total failure, return a structured error with manual instructions.

Detection is real (which/where + OS detection); actual installation is gated
behind dry_run so the platform never mutates a host during tests/demos.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..util.logger import get_logger

_log = get_logger("installer")

InstallMethod = Literal["apt", "pip", "cargo", "go", "npm", "brew", "winget", "git", "docker"]

_CASCADE: list[InstallMethod] = ["apt", "pip", "cargo", "go", "npm", "brew", "winget", "git", "docker"]

_METHOD_BIN: dict[InstallMethod, str] = {
    "apt": "apt-get",
    "pip": "pip",
    "cargo": "cargo",
    "go": "go",
    "npm": "npm",
    "brew": "brew",
    "winget": "winget",
    "git": "git",
    "docker": "docker",
}

_MATRIX: dict[str, dict[InstallMethod, str]] = {
    "nmap": {"apt": "apt-get install -y nmap", "brew": "brew install nmap", "winget": "winget install Insecure.Nmap"},
    "nikto": {"apt": "apt-get install -y nikto", "brew": "brew install nikto"},
    "gobuster": {"apt": "apt-get install -y gobuster", "go": "go install github.com/OJ/gobuster/v3@latest"},
    "ffuf": {"apt": "apt-get install -y ffuf", "go": "go install github.com/ffuf/ffuf/v2@latest"},
    "nuclei": {"go": "go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest", "pip": "pip install nuclei-cli"},
    "subfinder": {"go": "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"},
    "feroxbuster": {"cargo": "cargo install feroxbuster"},
    "rustscan": {"cargo": "cargo install rustscan"},
    "hydra": {"apt": "apt-get install -y hydra", "brew": "brew install hydra"},
    "sqlmap": {"apt": "apt-get install -y sqlmap", "pip": "pip install sqlmap"},
    "whatweb": {"apt": "apt-get install -y whatweb"},
    "semgrep": {"pip": "pip install semgrep"},
    "httpx": {"go": "go install github.com/projectdiscovery/httpx/cmd/httpx@latest"},
    "trivy": {"apt": "apt-get install -y trivy", "brew": "brew install trivy"},
    "sslscan": {"apt": "apt-get install -y sslscan", "brew": "brew install sslscan"},
    "testssl": {"apt": "apt-get install -y testssl.sh", "brew": "brew install testssl"},
    "wpscan": {"apt": "apt-get install -y wpscan"},
    "amass": {"apt": "apt-get install -y amass", "go": "go install github.com/owasp-amass/amass/v4/...@master"},
    "masscan": {"apt": "apt-get install -y masscan"},
    "radare2": {"apt": "apt-get install -y radare2", "brew": "brew install radare2"},
    "binwalk": {"apt": "apt-get install -y binwalk", "pip": "pip install binwalk"},
    "yara": {"apt": "apt-get install -y yara", "pip": "pip install yara-python"},
}


@dataclass(slots=True)
class InstallResult:
    installed: bool
    already_present: bool
    method: InstallMethod | None = None
    error: str | None = None
    manual_hint: str | None = None


class AutoInstaller:
    def __init__(self, dry_run: bool) -> None:
        self._dry_run = dry_run
        self._available: set[InstallMethod] | None = None

    def is_installed(self, tool: str) -> bool:
        return shutil.which(tool) is not None

    def available_methods(self) -> set[InstallMethod]:
        if self._available is None:
            self._available = {m for m, b in _METHOD_BIN.items() if shutil.which(b)}
        return self._available

    def detect_os(self) -> Literal["debian", "macos", "windows", "other"]:
        if sys.platform == "darwin":
            return "macos"
        if sys.platform.startswith("win"):
            return "windows"
        if Path("/etc/debian_version").exists():
            return "debian"
        try:
            rel = Path("/etc/os-release").read_text("utf-8")
            if any(d in rel.lower() for d in ("debian", "ubuntu", "kali")):
                return "debian"
        except OSError:
            pass
        return "other"

    def ensure(self, tool: str) -> InstallResult:
        t = tool.lower()
        if self.is_installed(t):
            return InstallResult(installed=True, already_present=True)

        available = self.available_methods()
        matrix = _MATRIX.get(t, {})
        for method in _CASCADE:
            if method not in available or method not in matrix:
                continue
            cmd = matrix[method]
            if self._dry_run:
                _log.info("[dry-run] would install '%s' via %s: %s", t, method, cmd)
                return InstallResult(installed=True, already_present=False, method=method)
            try:
                _log.info("installing '%s' via %s", t, method)
                subprocess.run(cmd, shell=True, check=True)
                if self.is_installed(t):
                    return InstallResult(installed=True, already_present=False, method=method)
            except subprocess.CalledProcessError as exc:
                _log.warning("install via %s failed: %s", method, exc)

        return InstallResult(
            installed=False,
            already_present=False,
            error=f"all install methods failed for '{t}'",
            manual_hint=f"Install '{t}' manually. Available methods on this host: {', '.join(sorted(available)) or 'none'}.",
        )
