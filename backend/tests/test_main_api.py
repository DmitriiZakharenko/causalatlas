"""
Phase 3 API-level tests: `POST /api/pipeline/{run_id}/decision` and the
`interventions` audit-trail field on `GET /api/pipeline/{run_id}/status`.
`claude_cli.run_orchestrator_stream` is fully mocked -- these never invoke
the real `claude` CLI, per the "environment now, live CLI tests later"
directive.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


def _poll_status_until(client: TestClient, run_id: str, statuses: set[str], timeout_s: float = 5.0) -> dict:
    """Synchronous tests can't `await` the background run task directly, and
    hitting the SSE `/stream` endpoint more than once per test trips a known
    sse-starlette + TestClient issue (a module-global exit-signal Event gets
    bound to the first request's event loop, then errors on the second
    request's loop). Polling `/status` sidesteps both: it's a plain request/
    response endpoint, and the mocked streams here resolve near-instantly
    (no real I/O), so a short poll loop is enough, never a real race.
    """
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = client.get(f"/api/pipeline/{run_id}/status").json()
        if last["status"] in statuses:
            return last
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached {statuses}, last seen: {last}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.db as db_mod
    import app.orchestrator as orch_mod
    from app.main import app

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(orch_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    # TestClient() outside a `with` block does not run the app's startup
    # lifespan (which normally calls db.init_db()) -- do it explicitly here.
    with TestClient(app) as c:
        yield c


async def _paused_stream(prompt, **kwargs):
    yield {
        "type": "result",
        "is_error": False,
        "result": "PAUSED_FOR_APPROVAL: agent10_novelty_verification \u2014 review needed",
    }


async def _resumed_stream(prompt, **kwargs):
    yield {"type": "result", "is_error": False, "total_cost_usd": 0.01, "duration_ms": 100, "result": "done"}


def test_decision_endpoint_404_for_unknown_run(client):
    resp = client.post("/api/pipeline/does_not_exist/decision", json={"decision": "approve"})
    assert resp.status_code == 404


def test_start_accepts_nested_target_and_persists_it(client, monkeypatch):
    import app.orchestrator as orch_mod

    async def _completes(prompt, **kwargs):
        yield {"type": "result", "is_error": False, "result": "done"}

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _completes)
    response = client.post(
        "/api/pipeline/run",
        json={
            "target": {
                "disease": "asthma",
                "genes": ["IL33"],
                "drugs": ["itepekimab"],
                "tissues": ["lung"],
                "cell_types": ["airway epithelial cell"],
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["target"]["drugs"] == ["itepekimab"]
    session_dir = orch_mod.SESSIONS_DIR / payload["run_id"]
    assert (session_dir / "drug_knowledge.json").exists()
    assert (session_dir / "target_context.json").exists()
    status = _poll_status_until(client, payload["run_id"], {"completed"})
    assert status["target_schema_version"] == "target.v1"


def test_decision_endpoint_422_for_invalid_decision_value(client, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _paused_stream)
    start = client.post("/api/pipeline/run", json={"disease": "Fake Disease"})
    run_id = start.json()["run_id"]
    resp = client.post(f"/api/pipeline/{run_id}/decision", json={"decision": "shrug"})
    assert resp.status_code == 422


def test_decision_endpoint_409_when_run_not_paused(client, monkeypatch):
    import app.orchestrator as orch_mod

    async def _completes_immediately(prompt, **kwargs):
        yield {"type": "result", "is_error": False, "result": "All done."}

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _completes_immediately)
    start = client.post("/api/pipeline/run", json={"disease": "Fake Disease"})
    run_id = start.json()["run_id"]
    _poll_status_until(client, run_id, {"completed"})

    resp = client.post(f"/api/pipeline/{run_id}/decision", json={"decision": "approve"})
    assert resp.status_code == 409


def test_decision_endpoint_resumes_paused_run_and_status_includes_interventions(client, monkeypatch):
    import app.orchestrator as orch_mod

    def _dispatch(prompt, **kwargs):
        return _resumed_stream(prompt, **kwargs) if kwargs.get("resume") else _paused_stream(prompt, **kwargs)

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _dispatch)
    start = client.post(
        "/api/pipeline/run", json={"disease": "Pausing Disease", "autonomy_level": "supervised"}
    )
    run_id = start.json()["run_id"]

    status = _poll_status_until(client, run_id, {"paused"})
    assert status["interventions"] == []

    resume_resp = client.post(
        f"/api/pipeline/{run_id}/decision", json={"decision": "approve", "note": "looks good"}
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "resumed"

    status = _poll_status_until(client, run_id, {"completed"})
    assert len(status["interventions"]) == 1
    assert status["interventions"][0]["decision"] == "approve"
    assert status["interventions"][0]["note"] == "looks good"
    assert status["interventions"][0]["agent_name"] == "agent10_novelty_verification"
