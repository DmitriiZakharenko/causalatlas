"""
Phase 1 Definition of Done (mandatory): "a unit test proves Agent 10's file alone
(with no other context) reproduces the H1/RESTATED and H2/Established
classification from Session 002 given the same two candidate hypotheses as
input."

This makes REAL `claude` CLI calls against the `agent10_novelty_verification`
subagent in isolation (via --agent, not via Task delegation from another
agent's context) -- no other agent's AGENTS.md or output is present. Costs real
subscription usage and ~30-120s wall clock per case, so it is marked `live_llm`
and excluded from default `pytest` runs (see pytest.ini). Run explicitly with:

    pytest -m live_llm tests/test_agent10_novelty.py -v

Verified passing manually during Phase 1 development (2026-07-01):
- H1 candidate -> classification "RESTATED", eligible_for_hypothesis_generation
  False, source_pmid "40184040" -- matches graph/novelty_audit.json's real
  H1_session001 entry exactly.
- H2 candidate -> classification "A", eligible_for_hypothesis_generation False
  -- matches graph/novelty_audit.json's real H2_session001 entry exactly.

Phase 1B addition, also verified passing manually (2026-07-01): a stream-json
run of the same H1 case shows Agent 10 spontaneously emitting a `Skill` tool_use
event for `novelty-verification-protocol` -- with NO explicit instruction in
the prompt to load any skill -- purely because its own AGENTS.md now
references the skill. This is the proof that Phase 1B's skill-loading
mechanism is real, observed runtime behavior, not just documentation that
sits unused.
"""
from __future__ import annotations

import asyncio

import pytest

from app.claude_cli import run_agent, run_agent_stream

NOVELTY_SCHEMA = {
    "type": "object",
    "properties": {
        "hypothesis_id": {"type": "string"},
        "classification": {"type": "string"},
        "eligible_for_hypothesis_generation": {"type": "boolean"},
        "step1_originality": {"type": "object"},
        "step2_external_searches": {"type": "array"},
    },
    "required": ["classification", "eligible_for_hypothesis_generation"],
}

# Verbatim candidate statements, taken from the real graph/novelty_audit.json
# entries H1_session001 / H2_session001 (see Agent 10's AGENTS.md fixtures).
H1_PROMPT = (
    "Run Agent 10's novelty verification protocol (Step 1 originality test, then "
    "Step 2 external search if needed) on this candidate hypothesis. "
    "hypothesis_id: H1_fixture. original_statement: 'cDC1 (Batf3-dependent) "
    "required for lung TRM sustaining chronic asthma'. Do not write any files -- "
    "just return the structured classification result."
)

H2_PROMPT = (
    "Run Agent 10's novelty verification protocol (Step 1 originality test, then "
    "Step 2 external search) on this candidate hypothesis. hypothesis_id: "
    "H2_fixture. original_statement: 'IL-33/ILC2/IL-5 couples airway to bone "
    "marrow eosinophilopoiesis'. This is a recombination of separately "
    "established sub-mechanisms, not a single-paper restatement, so it proceeds "
    "to Step 2 -- run real external searches to classify A-E. Do not write any "
    "files -- just return the structured classification result."
)


@pytest.mark.live_llm
def test_agent10_classifies_h1_as_restated():
    result = asyncio.run(
        run_agent("agent10_novelty_verification", H1_PROMPT, json_schema=NOVELTY_SCHEMA, timeout_s=180)
    )
    output = result.structured_output
    assert output is not None, f"no structured_output in: {result.raw}"
    assert output["classification"] == "RESTATED"
    assert output["eligible_for_hypothesis_generation"] is False


@pytest.mark.live_llm
def test_agent10_classifies_h2_as_established_a():
    result = asyncio.run(
        run_agent("agent10_novelty_verification", H2_PROMPT, json_schema=NOVELTY_SCHEMA, timeout_s=180)
    )
    output = result.structured_output
    assert output is not None, f"no structured_output in: {result.raw}"
    assert output["classification"].strip().upper().startswith("A")
    assert output["eligible_for_hypothesis_generation"] is False


@pytest.mark.live_llm
def test_agent10_spontaneously_loads_novelty_protocol_skill():
    """Phase 1B DoD: skill loading must be real runtime behavior. This prompt
    gives NO instruction to use any skill -- if Agent 10 loads
    `novelty-verification-protocol` anyway, that proves the AGENTS.md ->
    Skill-tool link works on its own, not just when hand-held."""

    async def _collect():
        events = []
        async for event in run_agent_stream("agent10_novelty_verification", H1_PROMPT):
            events.append(event)
        return events

    events = asyncio.run(_collect())

    skill_loads = [
        item
        for event in events
        for item in _tool_uses(event)
        if item.get("name") == "Skill"
    ]
    assert skill_loads, "Agent 10 never invoked the Skill tool"
    loaded_names = {su["input"].get("skill") for su in skill_loads}
    assert "novelty-verification-protocol" in loaded_names, (
        f"Agent 10 loaded skills {loaded_names}, expected novelty-verification-protocol among them"
    )

    result_events = [e for e in events if e.get("type") == "result"]
    assert result_events, f"no result event in stream: {events}"
    assert "RESTATED" in result_events[-1].get("result", "")


def _tool_uses(event: dict) -> list[dict]:
    """Recursively find every {"type": "tool_use", ...} dict nested in a
    stream-json event (Claude Code nests these inside message.content)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "tool_use":
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(event)
    return found
