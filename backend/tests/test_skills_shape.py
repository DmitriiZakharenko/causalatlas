"""
Phase 1B shape tests: verify the 5 canonical Skill files, skills_manifest.json,
and their generated native (.claude/skills/*) counterparts are structurally
sound and internally consistent with each other and with the agent registry.

Like test_agents_shape.py, this does not make a live model call -- it checks
that swapping a SKILL.md and re-running generate_native_agents.py produces the
right file, and that the manifest the orchestrator consults at runtime
(skills/skills_manifest.json) doesn't drift from the actual skill files or
reference an agent that doesn't exist.
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

from conftest import REPO_ROOT
from app.agent_registry import AGENT_ORDER, ORCHESTRATOR

ALL_AGENTS = {ORCHESTRATOR} | set(AGENT_ORDER)

MANIFEST_PATH = REPO_ROOT / "skills" / "skills_manifest.json"

with open(MANIFEST_PATH) as f:
    MANIFEST = json.load(f)

MANIFEST_SKILL_NAMES = [s["name"] for s in MANIFEST["skills"]]


def test_manifest_lists_exactly_five_skills():
    assert len(MANIFEST["skills"]) == 5
    assert set(MANIFEST_SKILL_NAMES) == {
        "pubmed-literature-search",
        "novelty-verification-protocol",
        "contradiction-detection",
        "graph-export-visualization",
        "cross-disease-motif-analysis",
    }


@pytest.mark.parametrize("skill_name", MANIFEST_SKILL_NAMES)
def test_manifest_entry_points_to_real_skill_file(skill_name: str):
    entry = next(s for s in MANIFEST["skills"] if s["name"] == skill_name)
    skill_path = REPO_ROOT / entry["path"]
    assert skill_path.exists(), f"manifest references missing file {skill_path}"
    assert entry["trigger_description"], f"{skill_name} has empty trigger_description"
    assert entry["used_by_agents"], f"{skill_name} lists no used_by_agents"


@pytest.mark.parametrize("skill_name", MANIFEST_SKILL_NAMES)
def test_manifest_used_by_agents_are_real_agents(skill_name: str):
    entry = next(s for s in MANIFEST["skills"] if s["name"] == skill_name)
    unknown = [a for a in entry["used_by_agents"] if a not in ALL_AGENTS]
    assert not unknown, f"{skill_name} used_by_agents references unknown agent(s): {unknown}"


@pytest.mark.parametrize("skill_name", MANIFEST_SKILL_NAMES)
def test_skill_md_has_frontmatter_and_required_sections(skill_name: str):
    path = REPO_ROOT / "skills" / skill_name / "SKILL.md"
    assert path.exists(), f"missing {path}"
    content = path.read_text()
    assert content.startswith("---\n"), "SKILL.md missing YAML frontmatter"
    frontmatter_raw = content.split("---\n", 2)[1]
    frontmatter = yaml.safe_load(frontmatter_raw)
    assert frontmatter["name"] == skill_name
    assert frontmatter["description"]
    assert "## When to use this skill" in content


@pytest.mark.parametrize("skill_name", MANIFEST_SKILL_NAMES)
def test_native_skill_generated_matches_source(skill_name: str):
    src = (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text()
    generated = REPO_ROOT / ".claude" / "skills" / skill_name / "SKILL.md"
    assert generated.exists(), f"missing generated {generated} -- run backend/generate_native_agents.py"
    assert generated.read_text() == src, f"{skill_name}: generated copy has drifted from source"


def test_pubmed_skill_cites_free_only_sources_not_google_scholar():
    content = (REPO_ROOT / "skills" / "pubmed-literature-search" / "SKILL.md").read_text()
    for must_have in [
        "eutils.ncbi.nlm.nih.gov",
        "api.semanticscholar.org",
        "api.openalex.org",
    ]:
        assert must_have in content, f"pubmed-literature-search missing required endpoint: {must_have}"
    assert re.search(r"[Nn]ever use Google Scholar", content), (
        "pubmed-literature-search must explicitly forbid Google Scholar"
    )


def test_novelty_protocol_references_two_source_rule():
    content = (REPO_ROOT / "skills" / "novelty-verification-protocol" / "SKILL.md").read_text()
    assert "pubmed-literature-search" in content
    assert "second source" in content.lower()


@pytest.mark.parametrize(
    "agent_name",
    ["agent01_literature_retrieval", "agent09_novelty_verification", "agent11_peer_review"],
)
def test_agents_md_no_longer_reference_google_scholar_as_a_source(agent_name: str):
    content = (REPO_ROOT / "agents" / agent_name / "AGENTS.md").read_text()
    # Google Scholar may only appear as part of an explicit prohibition, never as a
    # source instruction (e.g. "PubMed/Google Scholar/preprint servers").
    for line in content.splitlines():
        if "Google Scholar" in line:
            assert re.search(r"[Nn]ever|excluded|Do NOT|prohibit", line), (
                f"{agent_name}: 'Google Scholar' appears outside a prohibition context: {line!r}"
            )


def test_orchestrator_consults_skills_manifest():
    content = (REPO_ROOT / "agents" / ORCHESTRATOR / "AGENTS.md").read_text()
    assert "skills_manifest.json" in content
    for skill_name in MANIFEST_SKILL_NAMES:
        assert skill_name in content, f"orchestrator AGENTS.md never mentions {skill_name}"
