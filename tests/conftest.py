"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from figma_flutter_agent.dev.flutter_sdk import (
    flutter_sdk_root_from_agent_dotenv,
    resolve_flutter_executable,
)

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


def _patch_agent_debug_repo_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Keep agent ``.debug/`` writes out of the real checkout during unit tests."""
    monkeypatch.setattr(
        "figma_flutter_agent.debug.paths.agent_repo_root",
        lambda: root,
    )


@pytest.fixture(autouse=True)
def _isolate_agent_debug_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """Route all agent ``.debug/`` artifacts under per-test ``tmp_path`` (not the repo)."""
    if request.node.get_closest_marker("live_figma"):
        return
    _patch_agent_debug_repo_root(monkeypatch, tmp_path)


@pytest.fixture
def debug_agent_root(tmp_path: Path) -> Path:
    """Return the isolated agent repo root used for ``.debug/`` in this test."""
    return tmp_path


@pytest.fixture(autouse=True)
def _isolate_llm_env_from_os_environ(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Clear LLM-related os.environ entries for unit tests (live_figma keeps real secrets)."""
    if request.node.get_closest_marker("live_figma"):
        return
    for name in _LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _flutter_sdk_for_ast_sidecar_tests(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Expose Flutter SDK to AST sidecar tests (pytest skips loading ``.env``)."""
    if request.node.get_closest_marker("live_figma"):
        return
    if os.environ.get("FIGMA_FLUTTER_SDK") or os.environ.get("FLUTTER_ROOT"):
        return
    sdk_root = flutter_sdk_root_from_agent_dotenv()
    if sdk_root:
        monkeypatch.setenv("FIGMA_FLUTTER_SDK", sdk_root)
        return
    flutter = resolve_flutter_executable()
    if flutter is None:
        return
    monkeypatch.setenv("FIGMA_FLUTTER_SDK", str(Path(flutter).parent.parent))
