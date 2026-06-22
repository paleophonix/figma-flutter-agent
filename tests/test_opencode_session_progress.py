"""Tests for OpenCode session progress summarization."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.opencode_session_progress import (
    normalize_session_messages,
    summarize_opencode_progress,
)


def test_summarize_opencode_progress_tool_activity() -> None:
    messages = [
        {
            "parts": [
                {
                    "type": "tool",
                    "tool": "read",
                    "state": {
                        "status": "completed",
                        "input": {"filePath": "src/foo.py"},
                    },
                },
            ],
        },
    ]
    line = summarize_opencode_progress(messages)
    assert "tools=1" in line
    assert "read" in line
    assert "src/foo.py" in line


def test_summarize_opencode_progress_token_fallback() -> None:
    messages = [
        {"info": {"tokens": {"input": 120, "output": 45}}},
    ]
    assert summarize_opencode_progress(messages) == "LLM tokens in=120 out=45"


def test_summarize_opencode_progress_waiting() -> None:
    assert summarize_opencode_progress([]) == "waiting for OpenCode agent"


def test_normalize_session_messages_nested_payload() -> None:
    payload = {"messages": [{"role": "assistant", "parts": []}]}
    normalized = normalize_session_messages(payload)
    assert len(normalized) == 1
    assert normalized[0]["role"] == "assistant"
