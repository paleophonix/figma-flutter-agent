"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from figma_flutter_agent.dev.flutter_sdk import (
    flutter_sdk_root_from_agent_dotenv,
    resolve_flutter_executable,
)
from figma_flutter_agent.dev.opencode.worktree import (
    collect_repair_git_leaks,
    purge_repair_git_leaks,
)

_REAL_AGENT_REPO = Path(__file__).resolve().parents[1]

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


def _skip_repair_git_hygiene(request: pytest.FixtureRequest) -> bool:
    return bool(
        request.node.get_closest_marker("live_figma")
        or request.node.get_closest_marker("repair_live")
    )


def _agent_git_repo() -> Path | None:
    if (_REAL_AGENT_REPO / ".git").exists():
        return _REAL_AGENT_REPO
    return None


def _assert_repair_git_clean(phase: str) -> None:
    repo = _agent_git_repo()
    if repo is None:
        return
    worktrees, branches = collect_repair_git_leaks(repo)
    if not worktrees and not branches:
        return
    purge_repair_git_leaks(repo)
    worktrees, branches = collect_repair_git_leaks(repo)
    if worktrees or branches:
        pytest.fail(
            f"Repair git leaks after {phase}: worktrees={worktrees} branches={branches}. "
            "Close processes locking .worktrees/ or run pytest again."
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Drop stale repair worktrees/branches before the suite mutates git state."""
    del session
    repo = _agent_git_repo()
    if repo is not None:
        purge_repair_git_leaks(repo)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Verify the agent checkout has no repair worktrees or branches left behind."""
    del exitstatus
    if session.config.getoption("collectonly", default=False):
        return
    _assert_repair_git_clean("pytest session")


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


@pytest.fixture(autouse=True)
def _repair_git_hygiene_after_test(request: pytest.FixtureRequest) -> None:
    """Purge repair worktrees and ``repair/*`` branches after every unit test."""
    if _skip_repair_git_hygiene(request):
        yield
        return
    yield
    repo = _agent_git_repo()
    if repo is not None:
        purge_repair_git_leaks(repo)
    _assert_repair_git_clean(f"test {request.node.nodeid}")
