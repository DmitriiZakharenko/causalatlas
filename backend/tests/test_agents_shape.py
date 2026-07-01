"""
Phase 1 shape tests: one test case per agent (parametrized), asserting that
(a) its canonical AGENTS.md has every required section, and (b) the generated
native subagent registration file exists with correct frontmatter and the
least-privilege tool grant from app/agent_registry.py.

This intentionally does NOT make a live model call for every agent (that would
be slow, costly, and is explicitly out of scope per the build prompt: "not full
correctness -- that's Phase 2/3's job"). The one place full behavioral
correctness IS asserted against real historical data is
test_agent10_novelty.py's live_llm-marked test.
"""
from __future__ import annotations

import re

import pytest
import yaml

from conftest import REPO_ROOT
from app.agent_registry import AGENT_ORDER, AGENT_TOOLS, ORCHESTRATOR

ALL_AGENTS = [ORCHESTRATOR] + AGENT_ORDER

REQUIRED_SECTIONS = [
    "## Role",
    "## Inputs",
    "## Outputs",
    "## Hard constraints",
    "## Negative examples",
    "## Success criteria",
]


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_agents_md_has_required_sections(agent_name: str):
    path = REPO_ROOT / "agents" / agent_name / "AGENTS.md"
    assert path.exists(), f"missing {path}"
    content = path.read_text()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"{agent_name} AGENTS.md missing sections: {missing}"


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_agents_md_negative_example_is_grounded(agent_name: str):
    """Every Negative Examples section must cite at least one real PMID or a
    real session/report filename -- not a generic unsourced claim."""
    path = REPO_ROOT / "agents" / agent_name / "AGENTS.md"
    content = path.read_text()
    section = content.split("## Negative examples", 1)[1].split("## Success criteria", 1)[0]
    has_pmid = re.search(r"PMID\s*\d{5,}", section)
    has_source_file = re.search(r"`(reports|graph|data)/[^`]+`", section)
    assert has_pmid or has_source_file, (
        f"{agent_name}'s Negative Examples section cites no real PMID or source file"
    )


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_native_subagent_generated_with_correct_tools(agent_name: str):
    path = REPO_ROOT / ".claude" / "agents" / f"{agent_name}.md"
    assert path.exists(), f"missing generated {path} -- run backend/generate_native_agents.py"
    content = path.read_text()
    assert content.startswith("---\n"), "missing YAML frontmatter"
    frontmatter_raw = content.split("---\n", 2)[1]
    frontmatter = yaml.safe_load(frontmatter_raw)
    assert frontmatter["name"] == agent_name
    assert frontmatter["model"]
    expected_tools = set(AGENT_TOOLS.get(agent_name, []))
    actual_tools = set(frontmatter["tools"])
    assert actual_tools == expected_tools, (
        f"{agent_name} tool grant drifted: expected {expected_tools}, got {actual_tools}"
    )


def test_agent_order_matches_pipeline_spec():
    assert len(AGENT_ORDER) == 13, "pipeline must have exactly 13 agents (1-13)"
    assert AGENT_ORDER[0] == "agent01_baseline_canonical_knowledge"
    assert AGENT_ORDER[1] == "agent02_literature_retrieval"
    assert AGENT_ORDER[-1] == "agent13_experiment_design"
