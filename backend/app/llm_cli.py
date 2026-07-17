from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from app import claude_cli, codex_cli
from app.llm_common import AgentResult, LLMProviderError, get_llm_provider

__all__ = [
    "AgentResult",
    "LLMProviderError",
    "run_agent",
    "run_agent_stream",
    "run_orchestrator_stream",
]


def _backend():
    provider = get_llm_provider()
    if provider == "codex":
        return codex_cli
    return claude_cli


async def run_agent(
    agent_name: str,
    prompt: str,
    *,
    json_schema: dict | None = None,
    cwd: Path | None = None,
    timeout_s: float = 300.0,
) -> AgentResult:
    return await _backend().run_agent(
        agent_name, prompt, json_schema=json_schema, cwd=cwd, timeout_s=timeout_s
    )


async def run_agent_stream(
    agent_name: str,
    prompt: str,
    *,
    cwd: Path | None = None,
) -> AsyncIterator[dict]:
    async for event in _backend().run_agent_stream(agent_name, prompt, cwd=cwd):
        yield event


async def run_orchestrator_stream(
    prompt: str,
    *,
    cwd: Path | None = None,
    session_id: str | None = None,
    resume: bool = False,
) -> AsyncIterator[dict]:
    async for event in _backend().run_orchestrator_stream(
        prompt, cwd=cwd, session_id=session_id, resume=resume
    ):
        yield event

