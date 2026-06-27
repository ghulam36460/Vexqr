import asyncio

from aegix import Aegix
from aegix.core.store import RunRecord, SessionStore
from aegix.platform import AegixOptions


def test_store_records_run_and_artifacts():
    store = SessionStore(":memory:")
    app = Aegix(AegixOptions(client="custom", dry_run=True, store=store))
    result = asyncio.run(app.run("check if my web app is secure", "scanme.nmap.org"))

    runs = store.recent_runs()
    assert len(runs) == 1
    assert runs[0]["task_id"] == result.task_id
    assert runs[0]["status"] == "complete"

    detail = store.run_detail(result.task_id)
    assert len(detail["artifacts"]) > 0
    store.close()


def test_store_records_interventions_on_loop():
    store = SessionStore(":memory:")
    app = Aegix(
        AegixOptions(client="custom", dry_run=True, simulate_loop_on="nmap", store=store)
    )
    result = asyncio.run(app.run("full security assessment", "scanme.nmap.org"))
    detail = store.run_detail(result.task_id)
    # The forced loop must have produced at least one supervisor intervention.
    interventions = store._conn.execute(
        "SELECT COUNT(*) FROM interventions WHERE task_id=?", (result.task_id,)
    ).fetchone()[0]
    assert interventions >= 1
    assert detail["run"] is not None
    store.close()


def test_record_run_direct():
    store = SessionStore(":memory:")
    store.record_run(
        RunRecord(
            task_id="abc", client="custom", goal="g", target="t", status="complete",
            risk_label="LOW", risk_score=5, tokens_used=10, tokens_budget=100,
            started_at=1, finished_at=2,
        )
    )
    runs = store.recent_runs()
    assert runs[0]["risk_label"] == "LOW"
    store.close()
