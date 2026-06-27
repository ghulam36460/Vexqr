import asyncio

from aegix import Aegix
from aegix.platform import AegixOptions


def test_full_dry_run_assessment_completes():
    app = Aegix(AegixOptions(client="custom", dry_run=True))
    result = asyncio.run(app.run("check if my web app is secure", "scanme.nmap.org"))
    assert result.status == "complete"
    assert result.phases_completed == ["recon", "enumeration", "vuln_scan", "report"]
    assert any(a.kind == "port" for a in result.artifacts)
    assert any("CVE-2021-41773" in a.value for a in result.artifacts)


def test_supervisor_breaks_a_loop():
    # Force the worker to loop on nmap; the supervisor must redirect it and the
    # run must still complete rather than spin forever.
    app = Aegix(AegixOptions(client="custom", dry_run=True, simulate_loop_on="nmap"))
    result = asyncio.run(app.run("full security assessment", "scanme.nmap.org"))
    assert result.status in ("complete", "partial")
    assert "recon" in result.phases_completed
