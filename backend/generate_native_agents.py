"""
Generates native Claude Code subagent (.claude/agents/*.md) and skill
(.claude/skills/*/SKILL.md) registration files from the canonical source-of-truth
content in /agents/agentNN_<name>/AGENTS.md and /skills/<name>/SKILL.md.

Why this exists: Claude Code's own subagent/skill system (Task tool delegation,
`Skill` tool loading) is used directly as the context-engineering + orchestration
layer (see docs/architecture.md), instead of a hand-rolled Python ContextLoader.
This script is the only place that translates our project's required file layout
(build prompt: `/agents/agentNN_<name>/AGENTS.md`, `/skills/<name>/SKILL.md`) into
Claude Code's own convention (`.claude/agents/<name>.md`,
`.claude/skills/<name>/SKILL.md`). Editing an AGENTS.md or SKILL.md file and
re-running this script is what makes "swap one file, rerun, behavior changes"
(Phase 1 Definition of Done) true.

Usage:
    python3 backend/generate_native_agents.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_SRC = REPO_ROOT / "agents"
SKILLS_SRC = REPO_ROOT / "skills"
CLAUDE_AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
CLAUDE_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.agent_registry import AGENT_MODEL, AGENT_TOOLS  # noqa: E402


def first_paragraph(markdown: str) -> str:
    """Extract the '## Role' section's first paragraph for the subagent `description`."""
    match = re.search(r"##\s*Role\s*\n+(.+?)(?:\n\n|\n##)", markdown, re.S)
    if not match:
        return "LoopFinder pipeline agent."
    return " ".join(match.group(1).split())


def generate_agents() -> list[str]:
    written = []
    CLAUDE_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    for agent_dir in sorted(AGENTS_SRC.glob("agent*_*")):
        agents_md = agent_dir / "AGENTS.md"
        if not agents_md.exists():
            continue
        name = agent_dir.name  # e.g. agent09_novelty_verification
        content = agents_md.read_text()
        description = first_paragraph(content)
        tools = AGENT_TOOLS.get(name, ["Read", "Write"])
        frontmatter = (
            "---\n"
            + yaml.dump(
                {
                    "name": name,
                    "description": description,
                    "tools": tools,
                    "model": AGENT_MODEL,
                },
                default_flow_style=None,
                sort_keys=False,
            )
            + "---\n\n"
        )
        body = (
            f"You are `{name}` in the LoopFinder mechanistic-hypothesis pipeline. "
            f"The following is your complete, authoritative AGENTS.md specification "
            f"(source of truth: `/agents/{name}/AGENTS.md`). Follow it exactly, "
            f"including every Hard Constraint. When dispatched, you will also "
            f"receive the specific upstream JSON input and an output file path in "
            f"the task prompt -- write your structured JSON output to that exact "
            f"path using the Write tool, then return a short summary.\n\n"
            f"---\n\n{content}"
        )
        out_path = CLAUDE_AGENTS_DIR / f"{name}.md"
        out_path.write_text(frontmatter + body)
        written.append(str(out_path.relative_to(REPO_ROOT)))
    return written


def generate_skills() -> list[str]:
    written = []
    if not SKILLS_SRC.exists():
        return written
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for skill_dir in sorted(SKILLS_SRC.glob("*")):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        name = skill_dir.name
        content = skill_md.read_text()
        out_dir = CLAUDE_SKILLS_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "SKILL.md").write_text(content)
        written.append(str((out_dir / "SKILL.md").relative_to(REPO_ROOT)))
    return written


if __name__ == "__main__":
    agents_written = generate_agents()
    skills_written = generate_skills()
    print(json.dumps({"agents_generated": agents_written, "skills_generated": skills_written}, indent=2))
