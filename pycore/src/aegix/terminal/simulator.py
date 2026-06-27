"""Deterministic tool-output simulator for dry-run / offline mode.

Produces realistic raw output for common security tools so the full pipeline
(router -> execution -> parser -> supervisor) can be exercised without installing
or running real tools. When real execution is enabled this module is bypassed.
"""

from __future__ import annotations

import json
from typing import Any


def simulate_tool_output(tool: str, params: dict[str, Any]) -> str:
    host = str(params.get("host") or params.get("target") or "scanme.nmap.org")
    tool = tool.lower()
    if tool in ("nmap", "masscan"):
        return "\n".join(
            [
                "Starting Nmap 7.94 ( https://nmap.org )",
                f"Nmap scan report for {host} (45.33.32.156)",
                "Host is up (0.12s latency).",
                "PORT     STATE SERVICE     VERSION",
                "22/tcp   open  ssh         OpenSSH 6.6.1p1",
                "80/tcp   open  http        Apache httpd 2.4.7",
                "443/tcp  open  ssl/http    Apache httpd 2.4.7",
                "9929/tcp open  nping-echo  Nping echo",
                "Service detection performed.",
            ]
        )
    if tool in ("gobuster", "ffuf", "feroxbuster"):
        return "\n".join(
            [
                "=" * 63,
                "/admin                (Status: 301) [Size: 312]",
                "/login                (Status: 200) [Size: 1543]",
                "/api                  (Status: 200) [Size: 88]",
                "/.git                 (Status: 403) [Size: 277]",
                "=" * 63,
            ]
        )
    if tool == "nuclei":
        return "\n".join(
            [
                json.dumps({"template-id": "apache-version-detect", "host": host, "info": {"severity": "info"}}),
                json.dumps({"template-id": "CVE-2021-41773", "host": host, "info": {"severity": "critical"}}),
                json.dumps({"template-id": "exposed-git-config", "host": host, "info": {"severity": "high"}}),
            ]
        )
    if tool == "nikto":
        return "\n".join(
            [
                "- Nikto v2.5.0",
                "+ Server: Apache/2.4.7",
                "+ OSVDB-3268: /admin/: Directory indexing found.",
                "+ /login: Admin login page identified.",
            ]
        )
    if tool == "ghidra":
        return "\n".join(
            [
                "Ghidra headless analysis complete.",
                "Functions discovered: 142",
                "Entry point: 0x00401000",
                "Suspicious call: system() at 0x00401a3f",
                'String reference: "/bin/sh"',
                "Unsafe API: strcpy() at 0x00401b20",
            ]
        )
    if tool in ("subfinder", "amass"):
        return "\n".join([f"www.{host}", f"mail.{host}", f"dev.{host}", f"api.{host}"])
    if tool == "whatweb":
        return f"http://{host} [200 OK] Apache[2.4.7] PHP[5.5.9] jQuery[1.11.0] WordPress[5.2]"
    if tool == "httpx":
        return "\n".join(
            [
                json.dumps({"url": f"https://{host}", "status_code": 200, "title": "Login", "tech": ["Apache", "PHP"]}),
                json.dumps({"url": f"https://admin.{host}", "status_code": 401, "title": "Restricted"}),
            ]
        )
    if tool == "trivy":
        return "\n".join(
            [
                json.dumps({"VulnerabilityID": "CVE-2023-12345", "Severity": "HIGH", "PkgName": "openssl"}),
                json.dumps({"VulnerabilityID": "CVE-2022-99999", "Severity": "CRITICAL", "PkgName": "log4j"}),
            ]
        )
    if tool in ("sslscan", "testssl"):
        return "\n".join(
            [
                f"Testing SSL server {host} on port 443",
                "Accepted  TLSv1.0  112 bits  DES-CBC3-SHA",
                "  Heartbleed: VULNERABLE (CVE-2014-0160)",
                "  Certificate expired: yes",
            ]
        )
    if tool == "wpscan":
        return "\n".join(
            [
                "[+] WordPress version 5.2 identified",
                "[!] Title: WP < 5.2.3 - Vulnerable to XSS (CVE-2019-16223)",
                "[+] enumerating users: admin, editor",
            ]
        )
    if tool == "sqlmap":
        return "\n".join(
            [
                f"[*] testing connection to the target URL ({host})",
                "Parameter: id (GET)",
                "    Type: boolean-based blind",
                "[*] the back-end DBMS is MySQL",
                "available databases [2]: information_schema, app_db",
            ]
        )
    return f"[simulated output for '{tool}' against {host}] no findings parser matched; raw passthrough."
