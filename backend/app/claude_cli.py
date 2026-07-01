"""
Thin wrapper around headless Claude Code CLI invocations. This is the ONLY place
in the backend that shells out to `claude` -- no agent's business logic lives
here, and no direct Anthropic API calls are made anywhere in this codebase (see
docs/architecture.md). Every pipeline agent's actual behavior comes from its
`.claude/agents/<name>.md` registration (generated from `/agents/<name>/AGENTS.md`
by `generate_native_agents.py`).

Verified empirically (see Phase 1/1B chat history) before this was written:
- `claude -p --agent <name> ...` runs a named subagent directly, non-interactively.
- Headless tool calls (WebSearch/WebFetch/Task/Skill/...) are silently DENIED
  unless `--permission-mode bypassPermissions` and an explicit `--allowedTools`
  list are both passed -- this is not optional, it is required for Agent 10/12's
  live-search hard constraints to actually execute rather than fail closed.
- Auth is via the developer's existing Claude subscription (OAuth), not
  ANTHROPIC_API_KEY -- `--bare` mode is therefore never used here, since `--bare`
  forces API-key-only auth.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from app.agent_registry import tools_for

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ClaudeCliError(RuntimeError):
    """Raised when a `claude` invocation fails or its output can't be parsed.

    Per global constraint: callers must surface this to the user, never
    silently substitute a fabricated result.
    """


@dataclass
class AgentResult:
    agent_name: str
    result_text: str
    structured_output: dict | None
    cost_usd: float
    duration_ms: int
    raw: dict


def _build_command(
    agent_name: str,
    prompt: str,
    *,
    json_schema: dict | None = None,
    output_format: str = "json",
    extra_flags: list[str] | None = None,
) -> list[str]:
    tools = tools_for(agent_name)
    cmd = [
        "claude",
        "-p",
        "--agent",
        agent_name,
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        ",".join(tools),
        "--no-session-persistence",
        "--output-format",
        output_format,
    ]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema)]
    if extra_flags:
        cmd += extra_flags
    cmd.append(prompt)
    return cmd


async def run_agent(
    agent_name: str,
    prompt: str,
    *,
    json_schema: dict | None = None,
    cwd: Path | None = None,
    timeout_s: float = 300.0,
) -> AgentResult:
    """Run a single named subagent to completion and return its parsed result.

    Used for isolated agent invocations (e.g. the Phase 1 Agent 10 fixture test).
    For the full 12-agent pipeline run, see `run_orchestrator_stream` instead,
    which uses Agent 0's Task-tool delegation and streams progress.
    """
    cmd = _build_command(agent_name, prompt, json_schema=json_schema)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd or REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise ClaudeCliError(f"{agent_name} timed out after {timeout_s}s") from exc

    if proc.returncode != 0:
        raise ClaudeCliError(
            f"{agent_name} exited {proc.returncode}: {stderr.decode(errors='replace')}"
        )

    try:
        raw = json.loads(stdout.decode())
    except json.JSONDecodeError as exc:
        raise ClaudeCliError(
            f"{agent_name} did not return valid JSON: {stdout[:2000]!r}"
        ) from exc

    if raw.get("is_error"):
        raise ClaudeCliError(f"{agent_name} returned an error result: {raw}")

    return AgentResult(
        agent_name=agent_name,
        result_text=raw.get("result", ""),
        structured_output=raw.get("structured_output"),
        cost_usd=raw.get("total_cost_usd", 0.0),
        duration_ms=raw.get("duration_ms", 0),
        raw=raw,
    )


async def run_agent_stream(
    agent_name: str,
    prompt: str,
    *,
    cwd: Path | None = None,
) -> AsyncIterator[dict]:
    """Run any named subagent and yield each parsed stream-json line as it
    arrives. Unlike `run_agent` (output-format json), this exposes every
    intermediate tool_use event -- including `Skill` tool loads -- which is
    what proves skill-loading is real runtime behavior, not just a claim in
    AGENTS.md (see test_agent09_novelty.py's skill-loading regression test).
    """
    cmd = _build_command(
        agent_name,
        prompt,
        output_format="stream-json",
        extra_flags=["--verbose", "--include-partial-messages"],
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd or REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    async for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            yield {"type": "unparsed_line", "raw": line.decode(errors="replace")}
    await proc.wait()
    if proc.returncode != 0:
        stderr = await proc.stderr.read() if proc.stderr else b""
        yield {
            "type": "agent_failed",
            "returncode": proc.returncode,
            "stderr": stderr.decode(errors="replace"),
        }


async def run_orchestrator_stream(
    prompt: str,
    *,
    cwd: Path | None = None,
) -> AsyncIterator[dict]:
    """Run Agent 0 (orchestrator) and yield each parsed stream-json line as it
    arrives, for the caller (Phase 2's SSE endpoint) to translate into progress
    events. Never buffers the whole run before yielding -- the UI's live
    progress view depends on this being a true stream.
    """
    cmd = _build_command(
        "agent00_orchestrator",
        prompt,
        output_format="stream-json",
        extra_flags=["--verbose", "--include-partial-messages"],
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd or REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    async for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            yield {"type": "unparsed_line", "raw": line.decode(errors="replace")}
    await proc.wait()
    if proc.returncode != 0:
        stderr = await proc.stderr.read() if proc.stderr else b""
        yield {
            "type": "orchestrator_failed",
            "returncode": proc.returncode,
            "stderr": stderr.decode(errors="replace"),
        }
