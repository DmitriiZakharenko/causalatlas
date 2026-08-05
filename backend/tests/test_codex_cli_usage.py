from app.codex_cli import _extract_final_agent_message, _extract_usage


def test_extract_usage_reads_nested_codex_usage_without_cost_estimate():
    usage = _extract_usage(
        [
            {"type": "turn.started"},
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1200,
                    "cached_input_tokens": 300,
                    "output_tokens": 450,
                    "reasoning_tokens": 100,
                },
            },
        ]
    )

    assert usage["input_tokens"] == 1200
    assert usage["cached_input_tokens"] == 300
    assert usage["output_tokens"] == 450
    assert usage["reasoning_tokens"] == 100
    assert usage["total_tokens"] == 1650
    assert "cost_usd" not in usage
    assert usage["usage_source"] == "codex_cli_jsonl"


def test_extract_usage_prefers_latest_cumulative_record():
    usage = _extract_usage(
        [
            {"usage": {"input_tokens": 10, "output_tokens": 2}},
            {"usage": {"input_tokens": 100, "output_tokens": 20}, "total_cost_usd": None},
        ]
    )

    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["total_tokens"] == 120


def test_extract_final_agent_message_ignores_codex_transcript_events():
    assert _extract_final_agent_message(
        [
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "{\"ok\": true}"}},
            {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}},
        ]
    ) == '{"ok": true}'
