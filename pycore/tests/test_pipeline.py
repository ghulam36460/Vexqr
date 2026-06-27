from aegix.core.config import DEFAULT_CONFIG
from aegix.core.reporter import build_summary, risk_score
from aegix.core.types import TaskConstraints, TaskContext, TaskObject, Target
from aegix.supervisor.decomposer import TaskDecomposer
from aegix.terminal.parser import parse_tool_output
from aegix.terminal.simulator import simulate_tool_output


def _task(goal: str, max_tokens: int) -> TaskObject:
    return TaskObject(
        task_id="k",
        source_client="custom",
        request_type="recon",
        natural_input=goal,
        target=Target(host="x.test"),
        context=TaskContext(session_id="s"),
        constraints=TaskConstraints(max_tokens=max_tokens),
    )


def test_nmap_output_parses_ports():
    raw = simulate_tool_output("nmap", {"host": "scanme.nmap.org"})
    artifacts = parse_tool_output("nmap", raw)
    ports = [a.value for a in artifacts if a.kind == "port"]
    assert "22" in ports
    assert "80" in ports


def test_nuclei_extracts_findings():
    raw = simulate_tool_output("nuclei", {"host": "x.test"})
    artifacts = parse_tool_output("nuclei", raw)
    assert any("CVE-2021-41773" in a.value for a in artifacts)


def test_parser_extracts_secrets_generically():
    raw = "leaked key AKIAIOSFODNN7EXAMPLE found in config"
    artifacts = parse_tool_output("customtool", raw)
    assert any(a.kind == "secret" for a in artifacts)


def test_decomposer_infers_vuln_scan_phases():
    dec = TaskDecomposer(DEFAULT_CONFIG)
    plan = dec.plan(_task("check if my web app is secure", 100_000))
    phases = [p.phase for p in plan]
    assert phases == ["recon", "enumeration", "vuln_scan", "report"]
    total = sum(p.token_budget for p in plan)
    assert 90_000 < total <= 100_000


def test_decomposer_routes_binary_to_analysis():
    dec = TaskDecomposer(DEFAULT_CONFIG)
    phases = [p.phase for p in dec.plan(_task("help me debug this EXE", 50_000))]
    assert phases == ["analysis", "report"]


def test_reporter_risk_score_prioritizes():
    from aegix.core.types import Artifact

    arts = [Artifact("cve", "CVE-2021-41773"), Artifact("port", "80")]
    score, label = risk_score(arts)
    assert score > 0
    summary = build_summary(arts, ["recon", "vuln_scan", "report"])
    assert "Risk posture" in summary
