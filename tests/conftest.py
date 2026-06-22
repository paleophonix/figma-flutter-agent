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
    agent_worktree_parents,
    destroy_repair_worktree,
    prune_orphaned_worktrees,
)

_REAL_AGENT_REPO = Path(__file__).resolve().parents[1]

_REPAIR_WORKTREE_TEST_MODULES = frozenset(
    {
        "test_repair_check_gate",
        "test_repair_outer_loop",
        "test_step_gate",
        "test_pipeline_read_phase",
    },
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
    """Keep agent ``.debug/`` and repair worktrees out of the real checkout during unit tests."""
    monkeypatch.setattr(
        "figma_flutter_agent.debug.paths.agent_repo_root",
        lambda: root,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.config.paths.agent_repo_root",
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


def _repair_worktree_ids(repo: Path) -> frozenset[str]:
    ids: set[str] = set()
    for parent in agent_worktree_parents(repo):
        if not parent.is_dir():
            continue
        ids.update(path.name for path in parent.iterdir() if path.is_dir())
    return frozenset(ids)


@pytest.fixture(autouse=True)
def _cleanup_repair_worktrees_after_test(request: pytest.FixtureRequest) -> None:
    """Remove repair worktrees created during pipeline unit tests."""
    module_name = request.node.module.__name__.split(".")[-1] if request.node.module else ""
    if module_name not in _REPAIR_WORKTREE_TEST_MODULES:
        yield
        return
    if request.node.get_closest_marker("live_figma"):
        yield
        return

    repo = _REAL_AGENT_REPO
    before = _repair_worktree_ids(repo)
    yield
    after = _repair_worktree_ids(repo)
    for case_id in sorted(after - before):
        for parent in agent_worktree_parents(repo):
            candidate = parent / case_id
            if candidate.is_dir():
                destroy_repair_worktree(repo, candidate)
                break
    prune_orphaned_worktrees(repo)
