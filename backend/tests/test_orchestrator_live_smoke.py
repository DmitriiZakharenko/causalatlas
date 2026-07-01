"""
Phase 2 DoD: ONE live orchestrator integration smoke test (per the explicit
scope-trim instruction -- not one live test per agent). Proves the REAL
`agent00_orchestrator` (not a mock) actually performs real `Task` + `Skill`
tool dispatches when run via `claude_cli.run_orchestrator_stream`, and that
`app.orchestrator.StreamTranslator` correctly turns those real stream-json
events into the `agent_started` / `skill_loaded` / `agent_completed` /
`run_completed` events the rest of Phase 2 (SSE, DB, UI) is built on.

Deliberately constrained to ONE cheap agent dispatch + ONE skill load rather
than a full 13-agent run, to keep this specific test fast/cheap -- the full
end-to-end 13-agent run is validated separately (see the psoriasis/IL23A
dev-loop run kicked off alongside Phase 2, logged in data/sessions/).
"""
from __future__ import annotations

import asyncio

import pytest

from app.claude_cli import run_orchestrator_stream
from app.orchestrator import StreamTranslator

PROMPT = (
    "TEST HARNESS ONLY -- do not run the real 13-agent pipeline. Just do exactly these 2 "
    "things then stop immediately, do not do anything else: "
    "(1) load the 'graph-export-visualization' Skill via the Skill tool; "
    "(2) dispatch a Task to subagent 'agent13_experiment_design' with a trivial one-line "
    "prompt asking it to just reply with the single word 'ping' and do nothing else -- do "
    "not give it any real disease/gene target. "
    "After the Task returns, stop. Do not dispatch any other agent, do not write any files."
)


@pytest.mark.live_llm
def test_orchestrator_real_task_and_skill_dispatch_translate_correctly():
    async def _collect():
        translator = StreamTranslator()
        ui_events = []
        raw_events = []
        async for raw in run_orchestrator_stream(PROMPT):
            raw_events.append(raw)
            ui_events.extend(translator.feed(raw))
        return ui_events, raw_events

    ui_events, raw_events = asyncio.run(_collect())

    assert raw_events, "orchestrator produced no stream-json output at all"

    skill_events = [e for e in ui_events if e["type"] == "skill_loaded"]
    assert skill_events, f"orchestrator never loaded a skill (real events: {ui_events})"
    assert any(e["skill"] == "graph-export-visualization" for e in skill_events), skill_events

    started = [e for e in ui_events if e["type"] == "agent_started"]
    assert started, f"orchestrator never dispatched a Task (real events: {ui_events})"
    assert any(e["agent"] == "agent13_experiment_design" for e in started), started

    completed = [e for e in ui_events if e["type"] == "agent_completed"]
    assert completed, f"orchestrator's Task dispatch never produced a matched tool_result (real events: {ui_events})"
    assert any(e["agent"] == "agent13_experiment_design" for e in completed), completed

    terminal = [e for e in ui_events if e["type"] in ("run_completed", "run_failed")]
    assert terminal, f"no terminal event translated from the real run (real events: {ui_events})"
    assert terminal[-1]["type"] == "run_completed", f"orchestrator smoke run failed: {terminal[-1]}"
