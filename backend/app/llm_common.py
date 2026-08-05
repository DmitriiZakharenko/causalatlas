from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SUPPORTED_LLM_PROVIDERS = {"claude", "codex"}
DEFAULT_LLM_PROVIDER = "claude"


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider is invalid."""


@dataclass
class AgentResult:
    agent_name: str
    result_text: str
    structured_output: dict | None
    # Codex subscription runs do not necessarily expose billable USD. Keep
    # this nullable so the UI never presents an unavailable cost as $0.00.
    cost_usd: float | None
    duration_ms: int
    raw: dict
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str | None = None


def get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()
    if not provider:
        return DEFAULT_LLM_PROVIDER
    if provider not in SUPPORTED_LLM_PROVIDERS:
        raise LLMProviderError(
            f"Invalid LLM_PROVIDER={provider!r}; expected one of {sorted(SUPPORTED_LLM_PROVIDERS)}"
        )
    return provider


def codex_home_dir() -> Path:
    raw = os.getenv("CODEX_HOME")
    path = Path(raw) if raw else Path.home() / ".codex"
    path.mkdir(parents=True, exist_ok=True)
    return path


def agent_prompt_path(agent_name: str) -> Path:
    return REPO_ROOT / ".claude" / "agents" / f"{agent_name}.md"


def load_agent_prompt(agent_name: str) -> str:
    return agent_prompt_path(agent_name).read_text()


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return text
    body = parts[1]
    return body.lstrip("\n")


def codex_agent_prompt(agent_name: str, user_prompt: str) -> str:
    """Build a Codex prompt that embeds the same agent instructions Claude gets.

    Codex does not offer Claude Code's native `--agent`/Task-tool machinery, so
    the agent spec is injected directly into the prompt body instead.
    """
    agent_doc = strip_frontmatter(load_agent_prompt(agent_name))
    return (
        f"{agent_doc.rstrip()}\n\n"
        f"User prompt:\n{user_prompt.strip()}\n"
    )


def write_json_schema_file(schema: dict) -> Path:
    import json
    import tempfile as _tempfile

    with _tempfile.NamedTemporaryFile("w", suffix=".json", prefix="loopfinder_codex_schema_", delete=False) as fh:
        fh.write(json.dumps(schema, indent=2))
        schema_path = Path(fh.name)
    return schema_path
