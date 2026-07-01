"""
Phase 1 Definition of Done (mandatory): "a unit test proves Agent 9's file alone
(with no other context) reproduces the H1/RESTATED and H2/Established
classification from Session 002 given the same two candidate hypotheses as
input."

This makes REAL `claude` CLI calls against the `agent09_novelty_verification`
subagent in isolation (via --agent, not via Task delegation from another
agent's context) -- no other agent's AGENTS.md or output is present. Costs real
subscription usage and ~30-120s wall clock per case, so it is marked `live_llm`
and excluded from default `pytest` runs (see pytest.ini). Run explicitly with:

    pytest -m live_llm tests/test_agent09_novelty.py -v

Verified passing manually during Phase 1 development (2026-07-01):
- H1 candidate -> classification "RESTATED", eligible_for_hypothesis_generation
  False, source_pmid "40184040" -- matches graph/novelty_audit.json's real
  H1_session001 entry exactly.
- H2 candidate -> classification "A", eligible_for_hypothesis_generation False
  -- matches graph/novelty_audit.json's real H2_session001 entry exactly.
"""
from __future__ import annotations

import asyncio

import pytest

from app.claude_cli import run_agent

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
# entries H1_session001 / H2_session001 (see Agent 9's AGENTS.md fixtures).
H1_PROMPT = (
    "Run Agent 9's novelty verification protocol (Step 1 originality test, then "
    "Step 2 external search if needed) on this candidate hypothesis. "
    "hypothesis_id: H1_fixture. original_statement: 'cDC1 (Batf3-dependent) "
    "required for lung TRM sustaining chronic asthma'. Do not write any files -- "
    "just return the structured classification result."
)

H2_PROMPT = (
    "Run Agent 9's novelty verification protocol (Step 1 originality test, then "
    "Step 2 external search) on this candidate hypothesis. hypothesis_id: "
    "H2_fixture. original_statement: 'IL-33/ILC2/IL-5 couples airway to bone "
    "marrow eosinophilopoiesis'. This is a recombination of separately "
    "established sub-mechanisms, not a single-paper restatement, so it proceeds "
    "to Step 2 -- run real external searches to classify A-E. Do not write any "
    "files -- just return the structured classification result."
)


@pytest.mark.live_llm
def test_agent09_classifies_h1_as_restated():
    result = asyncio.run(
        run_agent("agent09_novelty_verification", H1_PROMPT, json_schema=NOVELTY_SCHEMA, timeout_s=180)
    )
    output = result.structured_output
    assert output is not None, f"no structured_output in: {result.raw}"
    assert output["classification"] == "RESTATED"
    assert output["eligible_for_hypothesis_generation"] is False


@pytest.mark.live_llm
def test_agent09_classifies_h2_as_established_a():
    result = asyncio.run(
        run_agent("agent09_novelty_verification", H2_PROMPT, json_schema=NOVELTY_SCHEMA, timeout_s=180)
    )
    output = result.structured_output
    assert output is not None, f"no structured_output in: {result.raw}"
    assert output["classification"].strip().upper().startswith("A")
    assert output["eligible_for_hypothesis_generation"] is False
