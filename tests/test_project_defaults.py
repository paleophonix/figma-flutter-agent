"""Tests for default Flutter project path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.project import (
    default_flutter_project_candidate,
    env_configured_project_dir,
    is_implicit_project_dir,
    resolve_implicit_project_dir,
)
from figma_flutter_agent.errors import FlutterProjectError


def test_is_implicit_project_dir() -> None:
    assert is_implicit_project_dir(Path(".")) is True
    assert is_implicit_project_dir(Path("/tmp/demo_app")) is False


def test_default_flutter_project_candidate_prefers_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_project = tmp_path / "from_env"
    env_project.mkdir()
    (env_project / "pubspec.yaml").write_text("name: env_app\n", encoding="utf-8")
    sibling = tmp_path / "demo_app"
    sibling.mkdir()
    (sibling / "pubspec.yaml").write_text("name: sibling_app\n", encoding="utf-8")

    monkeypatch.setattr(
        "figma_flutter_agent.dev.project._agent_repo_root",
        lambda: tmp_path / "agent_repo",
    )
    (tmp_path / "agent_repo").mkdir(exist_ok=True)

    assert default_flutter_project_candidate(env_project_dir=env_project) == env_project.resolve()


def test_default_flutter_project_candidate_falls_back_to_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sibling = tmp_path / "demo_app"
    sibling.mkdir()
    (sibling / "pubspec.yaml").write_text("name: sibling_app\n", encoding="utf-8")

    monkeypatch.setattr(
        "figma_flutter_agent.dev.project._agent_repo_root",
        lambda: tmp_path / "agent_repo",
    )
    (tmp_path / "agent_repo").mkdir(exist_ok=True)

    assert default_flutter_project_candidate(env_project_dir=None) == sibling.resolve()


def test_resolve_implicit_project_dir_validates_pubspec(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: app\n", encoding="utf-8")
    assert resolve_implicit_project_dir(env_project_dir=project) == project.resolve()


def test_resolve_implicit_project_dir_raises_when_missing_pubspec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()
    monkeypatch.setattr(
        "figma_flutter_agent.dev.project._agent_repo_root",
        lambda: tmp_path / "agent_repo",
    )
    (tmp_path / "agent_repo").mkdir(exist_ok=True)
    with pytest.raises(FlutterProjectError, match="Flutter project not found"):
        resolve_implicit_project_dir(env_project_dir=missing)


def test_env_configured_project_dir_reads_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("FIGMA_FLUTTER_PROJECT_DIR", str(workspace))
    assert env_configured_project_dir() == workspace.resolve()


def test_env_configured_project_dir_ignores_dot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_FLUTTER_PROJECT_DIR", ".")
    assert env_configured_project_dir() is None
