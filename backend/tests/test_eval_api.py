"""
Phase 4 API-level tests: `/api/eval/backfill`, `/api/eval/dashboard`,
`/api/eval/scores`, `/api/eval/judge/{run_id}`. `claude_cli.run_agent` is
fully mocked for the live-judge endpoint -- these never invoke the real
`claude` CLI.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.db as db_mod
    import app.eval as eval_mod
    import app.orchestrator as orch_mod
    from app.main import app

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(eval_mod, "EVAL_DIR", tmp_path / "eval")
    monkeypatch.setattr(orch_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    with TestClient(app) as c:
        yield c


def test_backfill_endpoint_scores_real_historical_sessions(client):
    resp = client.post("/api/eval/backfill")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scored"] == 5


def test_dashboard_endpoint_reflects_backfilled_scores(client):
    client.post("/api/eval/backfill")
    resp = client.get("/api/eval/dashboard")
    assert resp.status_code == 200
    metrics = resp.json()
    assert metrics["historical_gate_retroactive_catch_rate"] == 1.0
    assert "asthma_001" in metrics["sessions_covered"]


def test_scores_endpoint_filters_by_session_id(client):
    client.post("/api/eval/backfill")
    resp = client.get("/api/eval/scores", params={"session_id": "asthma_002"})
    assert resp.status_code == 200
    scores = resp.json()["scores"]
    assert len(scores) == 1
    assert scores[0]["hypothesis_id"] == "H-S002-01"


def test_backfill_endpoint_is_idempotent_over_http(client):
    client.post("/api/eval/backfill")
    client.post("/api/eval/backfill")
    resp = client.get("/api/eval/scores", params={"subject_type": "historical_backfill"})
    assert len(resp.json()["scores"]) == 5


def test_judge_endpoint_404_for_unknown_run(client):
    resp = client.post(
        "/api/eval/judge/does_not_exist",
        json={"hypothesis_id": "H-x", "statement": "s", "recombined_edges": []},
    )
    assert resp.status_code == 404


def test_judge_endpoint_409_when_run_not_completed(client, monkeypatch):
    import app.orchestrator as orch_mod

    async def _still_running(prompt, **kwargs):
        # never yields a terminal event within this test's lifetime
        yield {"type": "assistant", "message": {"content": []}}

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _still_running)
    start = client.post("/api/pipeline/run", json={"disease": "Still Running Disease"})
    run_id = start.json()["run_id"]

    resp = client.post(
        f"/api/eval/judge/{run_id}",
        json={"hypothesis_id": "H-x", "statement": "s", "recombined_edges": []},
    )
    assert resp.status_code == 409


def test_judge_endpoint_dispatches_mocked_judge_and_persists_score(client, monkeypatch):
    import app.eval as eval_mod
    import app.orchestrator as orch_mod
    from app.claude_cli import AgentResult

    async def _completes_immediately(prompt, **kwargs):
        yield {"type": "result", "is_error": False, "result": "All done."}

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _completes_immediately)
    start = client.post("/api/pipeline/run", json={"disease": "Completed Disease"})
    run_id = start.json()["run_id"]

    import time as time_mod

    deadline = time_mod.monotonic() + 5.0
    while time_mod.monotonic() < deadline:
        if client.get(f"/api/pipeline/{run_id}/status").json()["status"] == "completed":
            break
        time_mod.sleep(0.02)

    async def _fake_run_agent(agent_name, prompt, *, json_schema=None, **kwargs):
        return AgentResult(
            agent_name=agent_name,
            result_text="done",
            structured_output={
                "hypothesis_id": "H-x",
                "independent_classification": "E",
                "agrees_with_pipeline": True,
                "reasoning": "No prior art found after live searches.",
            },
            cost_usd=0.01,
            duration_ms=500,
            raw={},
        )

    monkeypatch.setattr(eval_mod.claude_cli, "run_agent", _fake_run_agent)

    resp = client.post(
        f"/api/eval/judge/{run_id}",
        json={"hypothesis_id": "H-x", "statement": "some statement", "recombined_edges": ["A -> B"]},
    )
    assert resp.status_code == 200
    assert resp.json()["verdict"]["independent_classification"] == "E"

    scores = client.get("/api/eval/scores", params={"subject_type": "live_judge"}).json()["scores"]
    assert len(scores) == 1
    assert scores[0]["outcome"] == "judge_agrees"
    assert scores[0]["session_id"] == run_id
