from __future__ import annotations

import asyncio


def test_llm_router_defaults_to_claude(monkeypatch):
    import app.llm_cli as llm_mod

    async def _fake_run_agent(*args, **kwargs):
        return ("claude", args, kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setattr(llm_mod.claude_cli, "run_agent", _fake_run_agent)

    result = asyncio.run(llm_mod.run_agent("agent03_publication_verification", "prompt"))
    assert result[0] == "claude"


def test_llm_router_switches_to_codex(monkeypatch):
    import app.llm_cli as llm_mod

    async def _fake_run_agent(*args, **kwargs):
        return ("codex", args, kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "codex")
    monkeypatch.setattr(llm_mod.codex_cli, "run_agent", _fake_run_agent)

    result = asyncio.run(llm_mod.run_agent("agent03_publication_verification", "prompt"))
    assert result[0] == "codex"


def test_codex_prompt_embeds_agent_spec_and_user_prompt():
    from app.llm_common import codex_agent_prompt

    prompt = codex_agent_prompt("agent03_publication_verification", "do the thing")
    assert "agent03_publication_verification" in prompt
    assert "do the thing" in prompt
    assert "Hard constraints" in prompt


def test_codex_agent05_prompt_uses_compact_inputs():
    from app.llm_common import codex_agent_prompt

    prompt = codex_agent_prompt("agent05_mechanistic_extraction", "input files:\n- compact")
    assert "publications_verified_compact.json" in prompt
    assert "quality_scores_compact.json" in prompt
    assert "publications_verified.json" not in prompt
    assert "quality_scores.json" not in prompt


def test_codex_normalizes_tool_event_aliases():
    from app.codex_cli import _normalize_node

    raw = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_call", "tool_name": "Skill", "input": {"skill": "pubmed-literature-search"}}
            ]
        },
    }
    normalized = _normalize_node(raw)
    assert normalized["message"]["content"][0]["type"] == "tool_use"
    assert normalized["message"]["content"][0]["name"] == "Skill"
