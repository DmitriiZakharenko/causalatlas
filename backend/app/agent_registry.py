"""
Single source of truth for which native Claude Code tools each pipeline agent is
granted, and the canonical agent ordering. Imported by both
`generate_native_agents.py` (build-time: writes .claude/agents/*.md) and
`app/claude_cli.py` (run-time: invokes `claude -p --agent <name> --allowedTools ...`)
so the two can never drift apart.
"""
from __future__ import annotations

AGENT_ORDER: list[str] = [
    "agent01_literature_retrieval",
    "agent02_publication_verification",
    "agent03_quality_filter",
    "agent04_mechanistic_extraction",
    "agent05_graph_builder",
    "agent06_loop_discovery",
    "agent07_topology_analysis",
    "agent08_contradiction_gap_detection",
    "agent09_novelty_verification",
    "agent10_hypothesis_generation",
    "agent11_peer_review",
    "agent12_experiment_design",
]

ORCHESTRATOR = "agent00_orchestrator"

# Least-privilege tool grants. Agents 1/9/11 are the only ones with a hard
# constraint requiring *live* external search (see their AGENTS.md files) --
# every other agent operates only on upstream JSON already on disk.
AGENT_TOOLS: dict[str, list[str]] = {
    ORCHESTRATOR: ["Task", "Skill", "Read", "Write", "Glob"],
    "agent01_literature_retrieval": ["WebSearch", "WebFetch", "Write"],
    "agent02_publication_verification": ["WebFetch", "Read", "Write"],
    "agent03_quality_filter": ["Read", "Write"],
    "agent04_mechanistic_extraction": ["Read", "Write"],
    "agent05_graph_builder": ["Read", "Write", "Glob"],
    "agent06_loop_discovery": ["Read", "Write"],
    "agent07_topology_analysis": ["Read", "Write"],
    "agent08_contradiction_gap_detection": ["Read", "Write"],
    "agent09_novelty_verification": ["WebSearch", "WebFetch", "Read", "Write", "Skill"],
    "agent10_hypothesis_generation": ["Read", "Write"],
    "agent11_peer_review": ["WebSearch", "WebFetch", "Read", "Write", "Skill"],
    "agent12_experiment_design": ["Read", "Write"],
}

AGENT_MODEL = "sonnet"


def tools_for(agent_name: str) -> list[str]:
    return AGENT_TOOLS.get(agent_name, ["Read", "Write"])
