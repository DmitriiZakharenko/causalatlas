"""
Phase 2 tests: stream-json -> UI-event translation, session/merge helpers, and
the RunManager's end-to-end wiring -- all against a MOCKED `claude_cli`, so
these run fast and deterministically in CI/normal `pytest` runs. The real
`claude` CLI is only exercised by the `live_llm`-marked tests (see
test_agent01_baseline.py, test_agent10_novelty.py, and the Phase 2 live smoke
test), consistent with this repo's separation of "structural/shape" tests from
"live LLM" tests.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app import db
from app.orchestrator import (
    RunManager,
    StreamTranslator,
    build_orchestrator_prompt,
    existing_graph_path,
    make_run_id,
    session_dir_for,
    slugify,
)


# ---------------------------------------------------------------------------
# StreamTranslator: raw claude stream-json -> UI progress events
# ---------------------------------------------------------------------------

def _tool_use_event(name: str, tool_input: dict, tool_id: str = "tu_1") -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]},
    }


def _tool_result_event(tool_id: str, content, is_error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content, "is_error": is_error}
            ]
        },
    }


def test_translator_emits_skill_loaded_for_skill_tool_use():
    t = StreamTranslator()
    events = t.feed(_tool_use_event("Skill", {"skill": "canonical-baseline-lookup"}))
    assert events == [{"type": "skill_loaded", "skill": "canonical-baseline-lookup"}]


def test_translator_ignores_empty_input_placeholder_from_partial_messages():
    """Real `--include-partial-messages` streams fire each tool_use twice: once
    as a `content_block_start` placeholder with `input: {}`, once fully
    populated. Discovered live (Phase 2 orchestrator smoke test) as duplicate
    "unknown_skill"/"unknown_agent" junk events reaching the UI -- the
    placeholder occurrence must be silently dropped, not translated."""
    t = StreamTranslator()
    placeholder = t.feed(_tool_use_event("Skill", {}, tool_id="tu_1"))
    assert placeholder == []
    real = t.feed(_tool_use_event("Skill", {"skill": "pubmed-literature-search"}, tool_id="tu_1"))
    assert real == [{"type": "skill_loaded", "skill": "pubmed-literature-search"}]


def test_translator_recognizes_agent_tool_name_not_just_task():
    """The real Claude Code CLI dispatches subagents via a tool literally named
    "Agent" (not "Task" as this project's docs assume) -- verified live via a
    raw stream-json dump during the Phase 2 orchestrator smoke test. Both
    names must be recognized since "Task" is still a distinct listed CLI
    capability and may be used in other CLI versions/configurations."""
    t = StreamTranslator()
    events = t.feed(
        _tool_use_event(
            "Agent",
            {"subagent_type": "agent02_literature_retrieval", "description": "corpus build"},
            tool_id="tu_agent_1",
        )
    )
    assert events == [
        {"type": "agent_started", "agent": "agent02_literature_retrieval", "description": "corpus build"}
    ]
    completed = t.feed(_tool_result_event("tu_agent_1", "done"))
    assert completed == [
        {"type": "agent_completed", "agent": "agent02_literature_retrieval", "is_error": False, "summary": "done"}
    ]


def test_translator_emits_agent_started_then_completed_for_task_pair():
    t = StreamTranslator()
    started = t.feed(
        _tool_use_event(
            "Task",
            {"subagent_type": "agent02_literature_retrieval", "description": "Run literature search"},
            tool_id="tu_42",
        )
    )
    assert len(started) == 1
    assert started[0]["type"] == "agent_started"
    assert started[0]["agent"] == "agent02_literature_retrieval"

    completed = t.feed(_tool_result_event("tu_42", "Found 120 PMIDs across 3 year bands."))
    assert len(completed) == 1
    assert completed[0]["type"] == "agent_completed"
    assert completed[0]["agent"] == "agent02_literature_retrieval"
    assert "120 PMIDs" in completed[0]["summary"]
    assert completed[0]["is_error"] is False


def test_translator_extracts_agent_name_from_prompt_when_subagent_type_missing():
    t = StreamTranslator()
    events = t.feed(
        _tool_use_event(
            "Task",
            {"description": "run baseline", "prompt": "Dispatch to agent01_baseline_canonical_knowledge now"},
            tool_id="tu_1",
        )
    )
    assert events[0]["agent"] == "agent01_baseline_canonical_knowledge"


def test_translator_ignores_non_task_non_skill_tool_use():
    t = StreamTranslator()
    events = t.feed(_tool_use_event("Read", {"file_path": "foo.json"}))
    assert events == []


def test_translator_unmatched_tool_result_produces_no_event():
    t = StreamTranslator()
    events = t.feed(_tool_result_event("never_seen_id", "some content"))
    assert events == []


def test_translator_run_completed_on_successful_result():
    t = StreamTranslator()
    events = t.feed({"type": "result", "is_error": False, "total_cost_usd": 0.42, "duration_ms": 1000, "result": "done"})
    assert events == [
        {"type": "run_completed", "cost_usd": 0.42, "duration_ms": 1000, "result_text": "done"}
    ]


def test_translator_preserves_nested_provider_usage_and_cost_alias():
    t = StreamTranslator()
    events = t.feed(
        {
            "type": "result",
            "is_error": False,
            "cost_usd": 0.17,
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
                "usage_source": "codex_cli_jsonl",
            },
            "result": "done",
        }
    )
    assert events == [
        {
            "type": "run_completed",
            "cost_usd": 0.17,
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "usage_source": "codex_cli_jsonl",
            "result_text": "done",
        }
    ]


def test_translator_run_failed_on_error_result():
    t = StreamTranslator()
    events = t.feed({"type": "result", "is_error": True, "result": "boom"})
    assert events == [{"type": "run_failed", "reason": "boom"}]


def test_translator_run_failed_on_synthetic_process_failure_event():
    t = StreamTranslator()
    events = t.feed({"type": "orchestrator_failed", "returncode": 1, "stderr": "permission denied"})
    assert events[0]["type"] == "run_failed"
    assert "permission denied" in events[0]["reason"]


def test_translator_run_paused_on_pause_marker_result():
    """Phase 3: a non-error `result` event whose text starts with the exact
    `PAUSED_FOR_APPROVAL:` marker (per agent00_orchestrator/AGENTS.md's
    pause protocol) must be translated to `run_paused`, not `run_completed`
    -- the two otherwise look identical (both non-error `result` events)."""
    t = StreamTranslator()
    events = t.feed(
        {
            "type": "result",
            "is_error": False,
            "result": "PAUSED_FOR_APPROVAL: agent10_novelty_verification \u2014 3 hypotheses classified B, review before promotion\n\nSummary: ...",
        }
    )
    assert events == [
        {
            "type": "run_paused",
            "agent": "agent10_novelty_verification",
            "reason": "agent10_novelty_verification \u2014 3 hypotheses classified B, review before promotion\n\nSummary: ...",
        }
    ]


def test_translator_run_completed_not_confused_with_pause_marker():
    t = StreamTranslator()
    events = t.feed({"type": "result", "is_error": False, "result": "All 13 agents completed successfully."})
    assert events[0]["type"] == "run_completed"


# ---------------------------------------------------------------------------
# Session / merge helpers
# ---------------------------------------------------------------------------

def test_slugify_normalizes_disease_names():
    assert slugify("Severe Asthma (Th2-high)") == "severe_asthma_th2_high"


def test_make_run_id_is_slug_plus_timestamp():
    run_id = make_run_id("Crohn's Disease")
    assert run_id.startswith("crohn_s_disease_")


def test_session_dir_for_creates_directory(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod, "SESSIONS_DIR", tmp_path / "sessions")
    d = session_dir_for("fake_run_001")
    assert d.exists()
    assert d.is_dir()


def test_existing_graph_path_none_when_absent(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    assert existing_graph_path("some_never_run_disease") is None


def test_existing_graph_path_found_triggers_merge_note(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    graphs_dir = tmp_path / "graphs"
    (graphs_dir / "asthma").mkdir(parents=True)
    (graphs_dir / "asthma" / "knowledge_graph.json").write_text("{}")
    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", graphs_dir)

    assert existing_graph_path("asthma") is not None
    prompt = build_orchestrator_prompt(
        run_id="asthma_test",
        disease="asthma",
        gene=None,
        autonomy_level="let_it_rip",
        session_dir=tmp_path,
    )
    assert "ALREADY EXISTS" in prompt
    assert "MERGE" in prompt


def test_build_orchestrator_prompt_retmax_override_for_dev_loop_runs(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    prompt = build_orchestrator_prompt(
        run_id="dev_loop_test",
        disease="a narrow gene-disease pair",
        gene="FAKE1",
        autonomy_level="let_it_rip",
        session_dir=tmp_path,
        pubmed_retmax_override=25,
    )
    assert "retmax=25" in prompt
    assert "COST-SCOPED DEV-LOOP RUN" in prompt
    assert "Do not change the skill file itself" in prompt


def test_build_orchestrator_prompt_no_retmax_note_by_default(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    prompt = build_orchestrator_prompt(
        run_id="demo_run_test",
        disease="asthma",
        gene=None,
        autonomy_level="let_it_rip",
        session_dir=tmp_path,
    )
    assert "COST-SCOPED DEV-LOOP RUN" not in prompt


def test_build_orchestrator_prompt_no_merge_note_for_new_disease(tmp_path, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    prompt = build_orchestrator_prompt(
        run_id="new_disease_test",
        disease="a brand new disease",
        gene="IL33",
        autonomy_level="supervised",
        session_dir=tmp_path,
    )
    assert "No prior knowledge graph exists" in prompt
    assert "gene: IL33" in prompt
    assert "autonomy_level: supervised" in prompt


# ---------------------------------------------------------------------------
# RunManager end-to-end wiring, with claude_cli mocked out entirely
# ---------------------------------------------------------------------------

FAKE_STREAM = [
    _tool_use_event("Skill", {"skill": "canonical-baseline-lookup"}, tool_id="s1"),
    _tool_use_event(
        "Task", {"subagent_type": "agent01_baseline_canonical_knowledge", "description": "baseline"}, tool_id="t1"
    ),
    _tool_result_event("t1", "baseline done"),
    {"type": "result", "is_error": False, "total_cost_usd": 0.01, "duration_ms": 500, "result": "pipeline complete"},
]


async def _fake_stream(prompt, **kwargs):
    for event in FAKE_STREAM:
        yield event


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    import app.db as db_mod
    import app.orchestrator as orch_mod

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "DB_PATH", db_path)
    monkeypatch.setattr(orch_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(orch_mod, "GRAPHS_DIR", tmp_path / "graphs")
    return db_path


async def test_run_manager_full_lifecycle_with_mocked_cli(isolated_env, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _fake_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Fake Disease", "IL33", "let_it_rip")

    events = []
    async for event in manager.subscribe(run_id):
        events.append(event)

    event_types = [e["type"] for e in events]
    assert event_types == ["skill_loaded", "agent_started", "agent_completed", "run_completed"]
    assert events[0]["skill"] == "canonical-baseline-lookup"
    assert events[1]["agent"] == "agent01_baseline_canonical_knowledge"
    assert events[3]["cost_usd"] == 0.01

    run = await db.get_run(run_id)
    assert run["status"] == "completed"
    assert run["disease"] == "Fake Disease"
    assert run["gene"] == "IL33"

    persisted = await db.get_events_since(run_id)
    assert [e["event_type"] for e in persisted] == event_types


async def test_run_manager_second_terminal_event_does_not_clobber_first_error(isolated_env, monkeypatch):
    """Real finding (Phase 2 dev-loop run hit an actual Claude subscription
    rate limit): `claude_cli.run_orchestrator_stream` can legitimately emit a
    "result" event with a real, informative failure reason, immediately
    followed by a synthetic `orchestrator_failed` wrapper (empty stderr) once
    the process exits non-zero. Only the first terminal event -- and its real
    error message -- must survive, both in `runs.error` and in the persisted
    event log (no duplicate `run_failed` rows)."""
    import app.orchestrator as orch_mod

    async def _rate_limited_stream(prompt, **kwargs):
        yield _tool_use_event("Skill", {"skill": "canonical-baseline-lookup"}, tool_id="s1")
        yield {"type": "result", "is_error": True, "result": "You've hit your limit · resets 11:30pm"}
        # Synthetic wrapper claude_cli.py emits when the process then exits
        # non-zero, with nothing new/useful in stderr this time.
        yield {"type": "orchestrator_failed", "returncode": 1, "stderr": ""}

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _rate_limited_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Rate Limited Disease", None, "let_it_rip")
    events = [e async for e in manager.subscribe(run_id)]

    failed_events = [e for e in events if e["type"] == "run_failed"]
    assert len(failed_events) == 1, f"expected exactly one run_failed event, got: {failed_events}"
    assert "hit your limit" in failed_events[0]["reason"]

    run = await db.get_run(run_id)
    assert run["status"] == "failed"
    assert "hit your limit" in run["error"], f"error was clobbered by the empty second event: {run['error']!r}"

    persisted = await db.get_events_since(run_id)
    assert [e["event_type"] for e in persisted].count("run_failed") == 1


async def test_run_manager_subscribe_replays_history_then_stops(isolated_env, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _fake_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Another Fake Disease", None, "let_it_rip")

    # Drain the run once so all events are persisted before we test replay.
    async for _ in manager.subscribe(run_id):
        pass

    # A brand-new subscriber (simulating a reconnecting UI) should see full history.
    replayed = [e async for e in manager.subscribe(run_id)]
    assert [e["type"] for e in replayed] == [
        "skill_loaded",
        "agent_started",
        "agent_completed",
        "run_completed",
    ]


async def test_start_run_persists_a_session_id(isolated_env, monkeypatch):
    """Phase 3: session_id must be generated and persisted at creation time
    (not parsed back out of the first stream event), so a run that pauses
    before any event even the very first checkpoint still has a resumable
    session_id on file."""
    import app.orchestrator as orch_mod

    captured_kwargs = {}

    async def _capturing_stream(prompt, **kwargs):
        captured_kwargs.update(kwargs)
        for event in FAKE_STREAM:
            yield event

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _capturing_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Session Id Disease", None, "let_it_rip")
    async for _ in manager.subscribe(run_id):
        pass

    run = await db.get_run(run_id)
    assert run["session_id"], "session_id must be persisted on the run row"
    assert captured_kwargs.get("session_id") == run["session_id"]


async def test_run_manager_pause_then_resume_full_lifecycle(isolated_env, monkeypatch):
    """Phase 3 end-to-end (mocked): a run that pauses must land in DB status
    'paused' with `current_agent` set from the pause marker, record a human
    intervention on resume, call claude_cli.run_orchestrator_stream a SECOND
    time with `resume=True` and the SAME session_id, and finish 'completed'."""
    import app.orchestrator as orch_mod

    PAUSE_RESULT = {
        "type": "result",
        "is_error": False,
        "result": "PAUSED_FOR_APPROVAL: agent10_novelty_verification \u2014 review needed",
    }
    resume_calls = []

    async def _first_stream(prompt, **kwargs):
        yield _tool_use_event("Skill", {"skill": "novelty-verification-protocol"}, tool_id="s1")
        yield PAUSE_RESULT

    async def _resume_stream(prompt, **kwargs):
        resume_calls.append({"prompt": prompt, **kwargs})
        yield {"type": "result", "is_error": False, "total_cost_usd": 0.02, "duration_ms": 200, "result": "All done."}

    def _dispatch_stream(prompt, **kwargs):
        if kwargs.get("resume"):
            return _resume_stream(prompt, **kwargs)
        return _first_stream(prompt, **kwargs)

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _dispatch_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Pausing Disease", "IL23A", "supervised")
    first_events = [e async for e in manager.subscribe(run_id)]
    assert first_events[-1]["type"] == "run_paused"
    assert first_events[-1]["agent"] == "agent10_novelty_verification"

    run = await db.get_run(run_id)
    assert run["status"] == "paused"
    assert run["current_agent"] == "agent10_novelty_verification"
    session_id_before = run["session_id"]
    assert session_id_before

    await manager.resume_run(run_id, "approve", note="looks fine")
    second_events = [e async for e in manager.subscribe(run_id, after_seq=first_events[-1]["seq"])]
    assert second_events[-1]["type"] == "run_completed"

    assert len(resume_calls) == 1
    assert resume_calls[0]["session_id"] == session_id_before
    assert resume_calls[0]["resume"] is True
    assert "APPROVE" in resume_calls[0]["prompt"]

    run = await db.get_run(run_id)
    assert run["status"] == "completed"
    assert run["session_id"] == session_id_before  # same session throughout


async def test_resume_run_rejects_non_paused_run(isolated_env, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _fake_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Not Paused Disease", None, "let_it_rip")
    async for _ in manager.subscribe(run_id):
        pass  # drains to "completed"

    with pytest.raises(ValueError, match="not paused"):
        await manager.resume_run(run_id, "approve")


async def test_resume_run_rejects_unknown_run_id(isolated_env):
    await db.init_db()
    manager = RunManager()
    with pytest.raises(ValueError, match="no run found"):
        await manager.resume_run("nonexistent_run_id", "approve")


async def test_retry_run_continues_a_failed_run_with_same_session(isolated_env, monkeypatch):
    """Found necessary live (2026-07-05): a run that fails mid-pipeline for a
    transient reason (e.g. the subscription's rolling usage cap) had no way
    to continue -- `retry_run` must resume the SAME session_id and land back
    in 'completed' on success."""
    import app.orchestrator as orch_mod

    retry_calls = []

    async def _first_stream(prompt, **kwargs):
        yield _tool_use_event("Agent", {"subagent_type": "agent01_baseline_canonical_knowledge"}, tool_id="a1")
        yield {"type": "result", "is_error": True, "result": "You've hit your limit"}

    async def _retry_stream(prompt, **kwargs):
        retry_calls.append({"prompt": prompt, **kwargs})
        yield {"type": "result", "is_error": False, "total_cost_usd": 0.03, "duration_ms": 300, "result": "Done."}

    def _dispatch_stream(prompt, **kwargs):
        if kwargs.get("resume"):
            return _retry_stream(prompt, **kwargs)
        return _first_stream(prompt, **kwargs)

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _dispatch_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Rate Limited Disease", "IL11", "let_it_rip")
    first_events = [e async for e in manager.subscribe(run_id)]
    assert first_events[-1]["type"] == "run_failed"

    run = await db.get_run(run_id)
    assert run["status"] == "failed"
    session_id_before = run["session_id"]
    assert session_id_before

    await manager.retry_run(run_id)
    second_events = [e async for e in manager.subscribe(run_id, after_seq=first_events[-1]["seq"])]
    assert second_events[-1]["type"] == "run_completed"

    assert len(retry_calls) == 1
    assert retry_calls[0]["session_id"] == session_id_before
    assert retry_calls[0]["resume"] is True
    assert run_id in retry_calls[0]["prompt"]

    run = await db.get_run(run_id)
    assert run["status"] == "completed"
    assert run["session_id"] == session_id_before  # same session throughout


async def test_retry_run_rejects_non_failed_run(isolated_env, monkeypatch):
    import app.orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _fake_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Not Failed Disease", None, "let_it_rip")
    async for _ in manager.subscribe(run_id):
        pass  # drains to "completed"

    with pytest.raises(ValueError, match="not failed"):
        await manager.retry_run(run_id)


async def test_retry_run_rejects_unknown_run_id(isolated_env):
    await db.init_db()
    manager = RunManager()
    with pytest.raises(ValueError, match="no run found"):
        await manager.retry_run("nonexistent_run_id")


async def test_subscribe_continues_after_retry_despite_prior_failure_in_history(
    isolated_env, monkeypatch
):
    """Mid-retry UI reconnect must not treat old run_failed rows as terminal."""
    import app.orchestrator as orch_mod

    gate = asyncio.Event()

    async def _first_stream(prompt, **kwargs):
        yield {"type": "result", "is_error": True, "result": "transient failure"}

    async def _retry_stream(prompt, **kwargs):
        yield _tool_use_event("Agent", {"subagent_type": "agent03_publication_verification"}, tool_id="a3")
        await gate.wait()
        yield _tool_result_event("a3", "verified")
        yield {"type": "result", "is_error": False, "total_cost_usd": 0.01, "duration_ms": 100, "result": "Done."}

    def _dispatch_stream(prompt, **kwargs):
        if kwargs.get("resume"):
            return _retry_stream(prompt, **kwargs)
        return _first_stream(prompt, **kwargs)

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _dispatch_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Reconnect Disease", "IL11", "let_it_rip")
    first_events = [e async for e in manager.subscribe(run_id)]
    assert first_events[-1]["type"] == "run_failed"

    await manager.retry_run(run_id)

    async def _collect():
        return [e async for e in manager.subscribe(run_id)]

    collector = asyncio.create_task(_collect())
    await asyncio.sleep(0.05)
    gate.set()
    replayed = await collector

    assert replayed[0]["type"] == "run_failed"
    assert replayed[-1]["type"] == "run_completed"
    assert any(e["type"] == "agent_started" for e in replayed)


async def test_run_manager_marks_run_failed_on_exception(isolated_env, monkeypatch):
    import app.orchestrator as orch_mod

    async def _broken_stream(prompt, **kwargs):
        raise RuntimeError("claude binary not found")
        yield {}  # pragma: no cover -- unreachable, keeps this an async generator

    monkeypatch.setattr(orch_mod.claude_cli, "run_orchestrator_stream", _broken_stream)
    await db.init_db()

    manager = RunManager()
    run_id = await manager.start_run("Broken Disease", None, "let_it_rip")

    events = [e async for e in manager.subscribe(run_id)]
    assert events[-1]["type"] == "run_failed"
    assert "claude binary not found" in events[-1]["reason"]

    run = await db.get_run(run_id)
    assert run["status"] == "failed"
    assert "claude binary not found" in run["error"]
