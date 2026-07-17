"""
Thin wrapper around the Codex CLI.

This backend mirrors the Claude-backed public API so the rest of the backend can
switch providers with `LLM_PROVIDER=codex` without changing the database/session
flow. Important limitation: Codex does not expose Claude Code's native Task
subagent tool, so the top-level orchestrator cannot get the same 13-subagent
dispatch granularity as the Claude backend. The code below therefore translates
Codex JSONL into the same coarse UI events where possible and otherwise falls
back to the final completion/result events.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

from app.llm_common import (
    AgentResult,
    REPO_ROOT,
    LLMProviderError,
    codex_agent_prompt,
    codex_home_dir,
)


class CodexCliError(LLMProviderError):
    """Raised when a `codex` invocation fails or its output can't be parsed."""


def _build_command(
    agent_name: str,
    prompt: str,
    *,
    json_schema: dict | None = None,
    output_format: str = "json",
    extra_flags: list[str] | None = None,
    session_id: str | None = None,
    resume: bool = False,
    output_last_message: Path | None = None,
) -> tuple[list[str], Path | None]:
    cmd = [
        "codex",
        "exec",
        "--json",
        "-C",
        str(REPO_ROOT),
        "--dangerously-bypass-approvals-and-sandbox",
        "--ignore-rules",
        "--disable",
        "standalone_web_search",
    ]
    if extra_flags:
        cmd += extra_flags

    # Codex's response-format schema validation is strict and rejects the
    # generic placeholder schema used by the existing pipeline. The backend
    # therefore relies on prompt-level JSON contracts and parses the final
    # result text instead of asking Codex to enforce a schema here.
    schema_path = None

    # Codex has a resume subcommand, but it does not share Claude Code's
    # session model or Task-tool-based orchestrator contract. Keep the backend
    # contract stable for the rest of LoopFinder by passing the full agent spec
    # in the prompt and letting the model continue from the persisted session
    # files when asked to resume.
    if session_id:
        prompt = f"LoopFinder session_id: {session_id}\nresume: {str(resume).lower()}\n\n{prompt}"

    # Prompt text can be large, so always feed it via stdin rather than argv.
    # `codex exec` supports `-` as the prompt sentinel for stdin input.
    cmd.append("-")
    return cmd, schema_path


def _normalize_node(node):
    if isinstance(node, dict):
        out = {k: _normalize_node(v) for k, v in node.items()}
        btype = out.get("type")
        if btype in {"tool_call", "function_call", "tool_use"}:
            out["type"] = "tool_use"
            if "name" not in out:
                name = out.get("tool_name") or out.get("tool") or out.get("function")
                if isinstance(name, str):
                    out["name"] = name
        elif btype in {"tool_result", "function_result"}:
            out["type"] = "tool_result"
        return out
    if isinstance(node, list):
        return [_normalize_node(v) for v in node]
    return node


def _extract_result_text(raw: dict) -> str | None:
    for key in ("result", "output", "text", "message"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            for nested_key in ("content", "text", "result"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested
        if isinstance(value, list):
            parts = [item.get("text", "") for item in value if isinstance(item, dict) and item.get("text")]
            if parts:
                return "\n".join(parts)
    return None


def _looks_like_terminal_result(raw: dict) -> bool:
    if raw.get("type") in {"result", "completed", "turn.completed", "response.completed"}:
        return True
    if isinstance(raw.get("result"), str) and raw["result"].strip():
        return True
    return False


async def _spawn_command(cmd: list[str], *, cwd: Path | None):
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "CODEX_HOME": str(codex_home_dir())},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def run_agent(
    agent_name: str,
    prompt: str,
    *,
    json_schema: dict | None = None,
    cwd: Path | None = None,
    timeout_s: float = 300.0,
) -> AgentResult:
    cmd, schema_path = _build_command(
        agent_name,
        prompt,
        json_schema=json_schema,
    )
    prompt_text = codex_agent_prompt(agent_name, prompt)
    proc = await _spawn_command(cmd, cwd=cwd)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=prompt_text.encode()), timeout=timeout_s)
        if proc.returncode != 0:
            raise CodexCliError(f"{agent_name} exited {proc.returncode}: {stderr.decode(errors='replace')}")

        structured_output = None
        result_text = ""
        for line in stdout.decode(errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            normalized = _normalize_node(event)
            if _looks_like_terminal_result(normalized):
                extracted = _extract_result_text(normalized)
                if extracted:
                    result_text = extracted
                if isinstance(normalized, dict) and normalized.get("structured_output") is not None:
                    structured_output = normalized.get("structured_output")
                break
        if not result_text:
            result_text = stdout.decode(errors="replace").strip()
        if structured_output is None and result_text:
            try:
                structured_output = json.loads(result_text)
            except json.JSONDecodeError:
                structured_output = None
        raw = {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
        }
        return AgentResult(
            agent_name=agent_name,
            result_text=result_text,
            structured_output=structured_output if isinstance(structured_output, dict) else None,
            cost_usd=0.0,
            duration_ms=0,
            raw=raw,
        )
    except asyncio.CancelledError:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    finally:
        if schema_path and schema_path.exists():
            schema_path.unlink(missing_ok=True)


async def run_agent_stream(
    agent_name: str,
    prompt: str,
    *,
    cwd: Path | None = None,
) -> AsyncIterator[dict]:
    cmd, schema_path = _build_command(agent_name, prompt, extra_flags=[])
    prompt_text = codex_agent_prompt(agent_name, prompt)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "CODEX_HOME": str(codex_home_dir())},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    try:
        if proc.stdin is not None:
            proc.stdin.write(prompt_text.encode())
            await proc.stdin.drain()
            proc.stdin.close()
        async for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "unparsed_line", "raw": line.decode(errors="replace")}
                continue
            normalized = _normalize_node(raw)
            if _looks_like_terminal_result(normalized):
                result_text = _extract_result_text(normalized)
                if result_text is not None:
                    yield {
                        "type": "result",
                        "is_error": bool(normalized.get("is_error", False)),
                        "result": result_text,
                        "total_cost_usd": normalized.get("total_cost_usd", 0.0),
                        "duration_ms": normalized.get("duration_ms", 0),
                    }
                    continue
            yield normalized
        await proc.wait()
        if proc.returncode != 0:
            stderr = await proc.stderr.read() if proc.stderr else b""
            yield {
                "type": "agent_failed",
                "returncode": proc.returncode,
                "stderr": stderr.decode(errors="replace"),
            }
    except asyncio.CancelledError:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    finally:
        if schema_path and schema_path.exists():
            schema_path.unlink(missing_ok=True)


async def run_orchestrator_stream(
    prompt: str,
    *,
    cwd: Path | None = None,
    session_id: str | None = None,
    resume: bool = False,
) -> AsyncIterator[dict]:
    # Delegate to the multi-agent Codex pipeline, which emits Claude-shaped raw
    # events for the existing StreamTranslator/UI layer while preserving the
    # original session/run directory contract.
    from app import codex_pipeline

    async for event in codex_pipeline.run_orchestrator_stream(
        prompt, cwd=cwd, session_id=session_id, resume=resume
    ):
        yield event
