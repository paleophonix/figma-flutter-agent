"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

_LLM_ENV_VARS = (
    "LLM_GENERATE_MODEL",
    "LLM_REPAIR_MODEL",
    "LLM_REFINE_MODEL",
    "LLM_MODEL",
    "LLM_PROVIDER",
    "LLM_TEMPERATURE",
    "LLM_TOP_P",
    "LLM_REQUIRE_STRICT_JSON_SCHEMA",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_llm_env_from_os_environ(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Clear LLM-related os.environ entries for unit tests (live_figma keeps real secrets)."""
    if request.node.get_closest_marker("live_figma"):
        return
    for name in _LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
