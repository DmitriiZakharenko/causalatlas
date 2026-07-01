"""
Phase 1B addition: proves Agent 1 (Baseline Canonical Knowledge) is real runtime
behavior, not just documentation -- mirrors test_agent10_novelty.py's
skill-loading proof.

This makes a REAL `claude` CLI call against the `agent01_baseline_canonical_knowledge`
subagent in isolation, with WebFetch allowed against the real Reactome/KEGG/UniProt/
MyDisease.info endpoints. Costs real subscription usage + external API calls, so it
is marked `live_llm` and excluded from default `pytest` runs (see pytest.ini). Run
explicitly with:

    pytest -m live_llm tests/test_agent01_baseline.py -v

Verified passing manually (2026-07-01): Agent 1, given a simple target with no
instruction to use any skill, spontaneously invoked the `Skill` tool for
`canonical-baseline-lookup`, then called WebFetch against at least one of the four
real endpoints and returned a `canonical_baseline.json`-shaped result with a real,
independently-checkable source identifier (not an invented one).
"""
from __future__ import annotations

import asyncio

import pytest

from app.claude_cli import run_agent_stream

PROMPT = (
    "Run Agent 1's baseline canonical knowledge lookup for disease: 'asthma', "
    "gene: 'IL33'. Query at least one of the four canonical sources (Reactome, "
    "KEGG, UniProt, MyDisease.info) for real. Do not write any files -- just "
    "return the structured canonical_baseline result with real source identifiers "
    "for whatever you actually found (or an honest zero-entries result if a "
    "source returned nothing)."
)


@pytest.mark.live_llm
def test_agent01_spontaneously_loads_canonical_baseline_skill_and_calls_real_endpoint():
    async def _collect():
        events = []
        async for event in run_agent_stream("agent01_baseline_canonical_knowledge", PROMPT):
            events.append(event)
        return events

    events = asyncio.run(_collect())

    tool_calls = [tu for event in events for tu in _tool_uses(event)]

    skill_loads = [tu for tu in tool_calls if tu.get("name") == "Skill"]
    assert skill_loads, "Agent 1 never invoked the Skill tool"
    loaded_names = {su["input"].get("skill") for su in skill_loads}
    assert "canonical-baseline-lookup" in loaded_names, (
        f"Agent 1 loaded skills {loaded_names}, expected canonical-baseline-lookup among them"
    )

    web_fetches = [tu for tu in tool_calls if tu.get("name") == "WebFetch"]
    assert web_fetches, "Agent 1 never called WebFetch against a real canonical-db endpoint"
    fetched_urls = [wf["input"].get("url", "") for wf in web_fetches]
    real_sources = ("reactome.org", "rest.kegg.jp", "rest.uniprot.org", "mydisease.info")
    assert any(src in url for url in fetched_urls for src in real_sources), (
        f"Agent 1's WebFetch calls did not hit any real canonical-db endpoint: {fetched_urls}"
    )

    result_events = [e for e in events if e.get("type") == "result"]
    assert result_events, f"no result event in stream: {events}"
    assert not result_events[-1].get("is_error"), f"Agent 1 run errored: {result_events[-1]}"


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
