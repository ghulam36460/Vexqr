from aegix.terminal.parser import parse_tool_output
from aegix.terminal.simulator import simulate_tool_output
from aegix.util.ids import fnv1a


def test_httpx_parses_urls_and_tech():
    raw = simulate_tool_output("httpx", {"host": "x.test"})
    arts = parse_tool_output("httpx", raw)
    assert any(a.kind == "path" for a in arts)
    assert any(a.kind == "tech" for a in arts)


def test_trivy_extracts_cves():
    raw = simulate_tool_output("trivy", {"host": "img:latest"})
    arts = parse_tool_output("trivy", raw)
    cves = [a.value for a in arts if a.kind == "cve"]
    assert "CVE-2022-99999" in cves
    assert any("critical" in (a.detail or "") for a in arts)


def test_sslscan_flags_heartbleed():
    raw = simulate_tool_output("sslscan", {"host": "x.test"})
    arts = parse_tool_output("sslscan", raw)
    assert any("severity=critical" in (a.detail or "") for a in arts)


def test_wpscan_flags_vulns():
    raw = simulate_tool_output("wpscan", {"host": "x.test"})
    arts = parse_tool_output("wpscan", raw)
    assert any(a.kind == "finding" for a in arts)


def test_sqlmap_confirms_injection():
    raw = simulate_tool_output("sqlmap", {"host": "http://x.test/?id=1"})
    arts = parse_tool_output("sqlmap", raw)
    assert any("SQL injection" in a.value for a in arts)


def test_fnv1a_matches_known_vector():
    # FNV-1a 64-bit of empty string is the offset basis.
    assert fnv1a("") == 14695981039346656037
    # Deterministic and stable.
    assert fnv1a("nmap|x.test||") == fnv1a("nmap|x.test||")
