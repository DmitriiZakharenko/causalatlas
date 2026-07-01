"""
Single source of truth for which native Claude Code tools each pipeline agent is
granted, and the canonical agent ordering. Imported by both
`generate_native_agents.py` (build-time: writes .claude/agents/*.md) and
`app/claude_cli.py` (run-time: invokes `claude -p --agent <name> --allowedTools ...`)
so the two can never drift apart.

Pipeline is 13 agents (Agent 1-13) + the orchestrator. Agent 1 (Baseline
Canonical Knowledge) was inserted ahead of literature retrieval so every
downstream agent has a canonical-database scaffold (Reactome/KEGG/UniProt/
MyDisease.info via the `canonical-baseline-lookup` skill) before any
PMID-derived content exists -- see agents/agent01_baseline_canonical_knowledge/AGENTS.md.
"""
from __future__ import annotations

AGENT_ORDER: list[str] = [
    "agent01_baseline_canonical_knowledge",
    "agent02_literature_retrieval",
    "agent03_publication_verification",
    "agent04_quality_filter",
    "agent05_mechanistic_extraction",
    "agent06_graph_builder",
    "agent07_loop_discovery",
    "agent08_topology_analysis",
    "agent09_contradiction_gap_detection",
    "agent10_novelty_verification",
    "agent11_hypothesis_generation",
    "agent12_peer_review",
    "agent13_experiment_design",
]

ORCHESTRATOR = "agent00_orchestrator"

# Least-privilege tool grants. Agents 1/2/10/12 are the only ones with a hard
# constraint requiring *live* external lookups/search (see their AGENTS.md
# files) -- every other agent operates only on upstream JSON already on disk.
AGENT_TOOLS: dict[str, list[str]] = {
    ORCHESTRATOR: ["Task", "Skill", "Read", "Write", "Glob"],
    "agent01_baseline_canonical_knowledge": ["WebFetch", "Read", "Write", "Skill"],
    "agent02_literature_retrieval": ["WebSearch", "WebFetch", "Write", "Skill"],
    "agent03_publication_verification": ["WebFetch", "Read", "Write"],
    "agent04_quality_filter": ["Read", "Write"],
    "agent05_mechanistic_extraction": ["Read", "Write"],
    "agent06_graph_builder": ["Read", "Write", "Glob", "Skill"],
    "agent07_loop_discovery": ["Read", "Write"],
    "agent08_topology_analysis": ["Read", "Write", "Skill"],
    "agent09_contradiction_gap_detection": ["Read", "Write", "Skill"],
    "agent10_novelty_verification": ["WebSearch", "WebFetch", "Read", "Write", "Skill"],
    "agent11_hypothesis_generation": ["Read", "Write"],
    "agent12_peer_review": ["WebSearch", "WebFetch", "Read", "Write", "Skill"],
    "agent13_experiment_design": ["Read", "Write"],
}

AGENT_MODEL = "sonnet"


def tools_for(agent_name: str) -> list[str]:
    return AGENT_TOOLS.get(agent_name, ["Read", "Write"])
