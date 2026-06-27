from sentinel.core.types import Artifact, ToolCall
from sentinel.supervisor.loop_detector import LoopDetector
from sentinel.supervisor.progress_scorer import ProgressScorer
from sentinel.supervisor.state import create_state, merge_artifacts, record_call
from sentinel.supervisor.token_budget import TokenBudgetManager


def _call(tool: str, host: str) -> ToolCall:
    return ToolCall(call_id="t", agent_id="a", task_id="k", phase="enumeration", tool=tool, params={"host": host})


def test_loop_detector_fires_after_threshold():
    det = LoopDetector(3)
    state = create_state("a", "k", "enumeration", 1000)
    verdict = None
    for _ in range(3):
        c = _call("gobuster", "host.test")
        record_call(state, c)
        verdict = det.check(state, c)
    assert verdict is not None and verdict.looping is True
    assert "gobuster" in verdict.message


def test_loop_detector_tolerant_for_recon():
    det = LoopDetector(3)
    state = create_state("a", "k", "recon", 1000)
    verdict = None
    for _ in range(3):
        c = ToolCall(call_id="t", agent_id="a", task_id="k", phase="recon", tool="nmap", params={"host": "host.test"})
        record_call(state, c)
        verdict = det.check(state, c)
    assert verdict is not None and verdict.looping is False


def test_loop_detector_exploit_fires_sooner():
    det = LoopDetector(3)  # exploit threshold = base - 1 = 2
    state = create_state("a", "k", "exploit", 1000)
    verdict = None
    for _ in range(2):
        c = ToolCall(call_id="t", agent_id="a", task_id="k", phase="exploit", tool="hydra", params={"host": "host.test"})
        record_call(state, c)
        verdict = det.check(state, c)
    assert verdict is not None and verdict.looping is True


def test_progress_scorer_flags_low_productivity():
    scorer = ProgressScorer(5)
    state = create_state("a", "k", "vuln_scan", 1000)
    merge_artifacts(state, [Artifact("finding", "x")])
    state.calls_since_last_artifact = 5
    v = scorer.check(state)
    assert v.productive is False
    assert v.phase_complete is True


def test_token_budget_escalates():
    mgr = TokenBudgetManager(0.15)
    s1 = create_state("a", "k", "recon", 1000)  # effective 850
    assert mgr.consume(s1, 400).level == "monitor"
    s2 = create_state("b", "k", "recon", 1000)
    assert mgr.consume(s2, 620).level == "warn"
    s3 = create_state("c", "k", "recon", 1000)
    v = mgr.consume(s3, 800)
    assert v.level == "force_wrap"
    assert v.stop is True


def test_merge_artifacts_dedups():
    state = create_state("a", "k", "recon", 1000)
    a = [Artifact("port", "22"), Artifact("port", "22"), Artifact("port", "80")]
    novel = merge_artifacts(state, a)
    assert len(novel) == 2
    assert len(state.artifacts) == 2
    assert state.calls_since_last_artifact == 0
