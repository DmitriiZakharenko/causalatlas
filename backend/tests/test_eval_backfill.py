"""
Phase 4 tests: `backfill_historical_sessions` and `compute_dashboard_metrics`.

Deliberately does NOT mock the session files themselves -- per an explicit
project constraint ("Phase 4 depends on these 3 sessions being real
historical data"), these tests assert against the REAL, already-committed
`data/graphs/asthma/novelty_audit.json`, `reports/session_002_report.json`,
and `reports/session_003_report.json`. Only the DB path is isolated (so a
test run never writes to the real `data/loopfinder.db`), and only
`eval.EVAL_DIR` is redirected (so a test run never overwrites the real
`eval/historical_backfill.json` artifact).
"""
from __future__ import annotations

import yaml
import pytest

from app import db, eval as eval_mod
from app.agent_registry import AGENT_ORDER, AGENT_TOOLS, EVAL_JUDGE
from conftest import REPO_ROOT


# ---------------------------------------------------------------------------
# agent14_eval_judge shape (mirrors test_agents_shape.py's pattern for the
# 13 pipeline agents) -- kept here rather than in that file since this agent
# is deliberately NOT part of AGENT_ORDER (see agent_registry.py).
# ---------------------------------------------------------------------------

def test_eval_judge_not_part_of_pipeline_sequence():
    assert EVAL_JUDGE not in AGENT_ORDER


def test_eval_judge_agents_md_has_required_sections():
    content = (REPO_ROOT / "agents" / EVAL_JUDGE / "AGENTS.md").read_text()
    for section in ["## Role", "## Inputs", "## Outputs", "## Hard constraints", "## Negative examples", "## Success criteria"]:
        assert section in content, f"agent14_eval_judge AGENTS.md missing {section}"


def test_eval_judge_agents_md_mandates_blind_grading():
    content = (REPO_ROOT / "agents" / EVAL_JUDGE / "AGENTS.md").read_text()
    assert "Blind grading" in content or "blind" in content.lower()


def test_eval_judge_has_no_write_tool_grant():
    """Read-only auditor per its own AGENTS.md hard constraint -- must never
    be able to modify a pipeline session file or the knowledge graph."""
    assert "Write" not in AGENT_TOOLS[EVAL_JUDGE]


def test_eval_judge_native_agent_generated_with_correct_tools():
    path = REPO_ROOT / ".claude" / "agents" / f"{EVAL_JUDGE}.md"
    assert path.exists(), f"missing generated {path} -- run backend/generate_native_agents.py"
    content = path.read_text()
    frontmatter = yaml.safe_load(content.split("---\n", 2)[1])
    assert frontmatter["name"] == EVAL_JUDGE
    assert set(frontmatter["tools"]) == set(AGENT_TOOLS[EVAL_JUDGE])


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod
    import app.eval as eval_module

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(eval_module, "EVAL_DIR", tmp_path / "eval")
    return tmp_path


async def test_backfill_scores_exactly_five_real_hypotheses(isolated_db):
    await db.init_db()
    records = await eval_mod.backfill_historical_sessions()
    assert len(records) == 5

    by_id = {r["hypothesis_id"]: r for r in records}
    assert set(by_id) == {"H1_session001", "H2_session001", "H-S002-01", "H-D001", "H-C002"}


async def test_backfill_h1_h2_are_confirmed_false_positives_with_real_ground_truth(isolated_db):
    """H1/H2 are the founding failure case (immunology_pipeline.md's preamble)
    -- real re-audit ground truth from data/graphs/asthma/novelty_audit.json."""
    await db.init_db()
    records = await eval_mod.backfill_historical_sessions()
    by_id = {r["hypothesis_id"]: r for r in records}

    h1 = by_id["H1_session001"]
    assert h1["outcome"] == eval_mod.Outcome.CONFIRMED_FALSE_POSITIVE_HISTORICAL
    assert h1["ground_truth"] == "RESTATED"
    assert h1["session_id"] == "asthma_001"

    h2 = by_id["H2_session001"]
    assert h2["outcome"] == eval_mod.Outcome.CONFIRMED_FALSE_POSITIVE_HISTORICAL
    assert "Established consensus" in h2["ground_truth"]


async def test_backfill_session002_hypothesis_correctly_rejected(isolated_db):
    await db.init_db()
    records = await eval_mod.backfill_historical_sessions()
    by_id = {r["hypothesis_id"]: r for r in records}

    h = by_id["H-S002-01"]
    assert h["outcome"] == eval_mod.Outcome.CORRECTLY_REJECTED
    assert h["session_id"] == "asthma_002"
    assert "REJECT" in h["reasoning"]


async def test_backfill_session003_hypotheses_pending_not_fabricated(isolated_db):
    """H-D001/H-C002 passed peer review + got experiment designs but have no
    real wet-lab result anywhere in this repo -- must be marked PENDING, not
    scored as a correct/incorrect prediction (that would be fabricating a
    ground truth that doesn't exist)."""
    await db.init_db()
    records = await eval_mod.backfill_historical_sessions()
    by_id = {r["hypothesis_id"]: r for r in records}

    for hyp_id in ("H-D001", "H-C002"):
        r = by_id[hyp_id]
        assert r["outcome"] == eval_mod.Outcome.ACCEPTED_PENDING_VALIDATION
        assert r["ground_truth"] is None
        assert r["session_id"] == "asthma_003"


async def test_backfill_excludes_session_004_hardening(isolated_db):
    """Session 004 is explicitly excluded (include_in_eval_flywheel: false,
    see sessions_manifest.json's own notes) -- a graph-hardening pass with no
    hypotheses, deliberately out of Phase 4 scope per an earlier decision."""
    await db.init_db()
    records = await eval_mod.backfill_historical_sessions()
    assert all(r["session_id"] != "asthma_004_hardening" for r in records)


async def test_backfill_is_idempotent(isolated_db):
    """Re-running the backfill (e.g. a second POST /api/eval/backfill) must
    replace, not accumulate, the previous historical_backfill rows."""
    await db.init_db()
    await eval_mod.backfill_historical_sessions()
    records_second_run = await eval_mod.backfill_historical_sessions()
    persisted = await db.list_eval_scores(subject_type="historical_backfill")
    assert len(persisted) == len(records_second_run) == 5


async def test_backfill_writes_artifact_file(isolated_db):
    await db.init_db()
    await eval_mod.backfill_historical_sessions()
    artifact = isolated_db / "eval" / "historical_backfill.json"
    assert artifact.exists()


def test_dashboard_metrics_compute_100_percent_gate_catch_rate():
    """Both known historical false positives (H1 -> RESTATED, H2 -> A) are
    non-D/E under the CURRENT Agent 9 rule (only D/E may reach Agent 10) --
    so the current gate design would have retroactively caught 100% of the
    founding failure case. This is a computed fact from real ground_truth
    values, not an asserted claim."""
    records = [
        {
            "session_id": "asthma_001",
            "hypothesis_id": "H1_session001",
            "outcome": "confirmed_false_positive_historical",
            "ground_truth": "RESTATED",
        },
        {
            "session_id": "asthma_001",
            "hypothesis_id": "H2_session001",
            "outcome": "confirmed_false_positive_historical",
            "ground_truth": "A \u2014 Established consensus",
        },
        {
            "session_id": "asthma_002",
            "hypothesis_id": "H-S002-01",
            "outcome": "correctly_rejected",
            "ground_truth": None,
        },
    ]
    metrics = eval_mod.compute_dashboard_metrics(records)
    assert metrics["historical_gate_retroactive_catch_rate"] == 1.0
    assert metrics["total_scored"] == 3
    assert metrics["sessions_covered"] == ["asthma_001", "asthma_002"]
    assert metrics["outcome_counts"]["confirmed_false_positive_historical"] == 2


def test_dashboard_metrics_catch_rate_drops_if_a_false_positive_was_actually_novel():
    """Sanity check that the catch-rate calculation is a real computation, not
    a hardcoded 1.0 -- a ground_truth of D/E would correctly show the current
    gate design would NOT have caught that (hypothetical) case."""
    records = [
        {
            "session_id": "asthma_999",
            "hypothesis_id": "H-fake",
            "outcome": "confirmed_false_positive_historical",
            "ground_truth": "D \u2014 Partially established",
        },
    ]
    metrics = eval_mod.compute_dashboard_metrics(records)
    assert metrics["historical_gate_retroactive_catch_rate"] == 0.0


def test_dashboard_metrics_none_when_no_false_positives_scored():
    metrics = eval_mod.compute_dashboard_metrics([{"session_id": "x", "outcome": "correctly_rejected"}])
    assert metrics["historical_gate_retroactive_catch_rate"] is None


def test_dashboard_metrics_live_judge_agreement_rate():
    records = [
        {"session_id": "run1", "outcome": "judge_agrees"},
        {"session_id": "run1", "outcome": "judge_agrees"},
        {"session_id": "run1", "outcome": "judge_disagrees"},
    ]
    metrics = eval_mod.compute_dashboard_metrics(records)
    assert metrics["live_judge_agreement_rate"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Live judge: blind-prompt construction (structural, no model call) + a
# mocked end-to-end persistence test (claude_cli.run_agent fully mocked --
# zero real cost, per this project's standing "no live Claude calls unless
# explicitly requested" constraint).
# ---------------------------------------------------------------------------

def test_build_judge_prompt_withholds_pipeline_classification_label():
    """The whole point of the blind-grading protocol (see
    agents/agent14_eval_judge/AGENTS.md's Hard Constraints) is that the
    prompt never leaks what the pipeline itself decided -- assert this
    structurally so a future edit can't silently reintroduce the label."""
    prompt = eval_mod.build_judge_prompt(
        run_id="fake_run_001",
        hypothesis_id="H-fake",
        statement="Some candidate mechanism statement.",
        recombined_edges=["A -> B", "B -> C"],
    )
    assert "H-fake" in prompt
    assert "Some candidate mechanism statement." in prompt
    for leaked_label in ["RESTATED", "classification\": \"A", "classification\": \"D", "ACCEPT", "REJECT"]:
        assert leaked_label not in prompt


async def test_run_live_judge_persists_score_from_mocked_verdict(isolated_db, monkeypatch):
    import app.eval as eval_module
    from app.claude_cli import AgentResult

    async def _fake_run_agent(agent_name, prompt, *, json_schema=None, **kwargs):
        assert agent_name == eval_module.JUDGE_AGENT
        return AgentResult(
            agent_name=agent_name,
            result_text="done",
            structured_output={
                "hypothesis_id": "H-fake",
                "independent_classification": "B",
                "agrees_with_pipeline": False,
                "reasoning": "Found PMID 12345678 stating this exact chain already.",
            },
            cost_usd=0.01,
            duration_ms=1000,
            raw={},
        )

    monkeypatch.setattr(eval_module.claude_cli, "run_agent", _fake_run_agent)
    await db.init_db()

    verdict = await eval_mod.run_live_judge("fake_run_001", "H-fake", "statement", ["A -> B"])
    assert verdict["independent_classification"] == "B"

    persisted = await db.list_eval_scores(subject_type="live_judge")
    assert len(persisted) == 1
    assert persisted[0]["outcome"] == eval_mod.Outcome.JUDGE_DISAGREES
    assert persisted[0]["session_id"] == "fake_run_001"
    assert persisted[0]["hypothesis_id"] == "H-fake"
    assert persisted[0]["ground_truth"] == "B"
