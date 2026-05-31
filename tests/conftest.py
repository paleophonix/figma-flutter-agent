"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable

_LLM_ENV_VARS = (
    "LLM_GENERATE_MODEL",
    "LLM_REPAIR_MODEL",
    "LLM_REFINE_MODEL",
    "LLM_MODEL",
    "LLM_PROVIDER",
    "LLM_TEMPERATURE",
    "LLM_REPAIR_TEMPERATURE",
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


def _flutter_sdk_root_from_agent_dotenv() -> str | None:
    env_path = agent_repo_root() / ".env"
    if not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "FIGMA_FLUTTER_SDK":
            continue
        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None
    return None


@pytest.fixture(autouse=True)
def _flutter_sdk_for_ast_sidecar_tests(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Expose Flutter SDK to AST sidecar tests (pytest skips loading ``.env``)."""
    if request.node.get_closest_marker("live_figma"):
        return
    if os.environ.get("FIGMA_FLUTTER_SDK") or os.environ.get("FLUTTER_ROOT"):
        return
    sdk_root = _flutter_sdk_root_from_agent_dotenv()
    if sdk_root:
        monkeypatch.setenv("FIGMA_FLUTTER_SDK", sdk_root)
        return
    flutter = resolve_flutter_executable()
    if flutter is None:
        return
    monkeypatch.setenv("FIGMA_FLUTTER_SDK", str(Path(flutter).parent.parent))
