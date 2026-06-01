"""Tests for multi-project workspace resolution under FIGMA_FLUTTER_PROJECT_DIR."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.project import (
    active_project_relative_path,
    default_flutter_project_candidate,
    discover_flutter_projects,
    ensure_batch_manifest,
    has_batch_manifest,
    infer_figma_file_key_for_manifest,
    resolve_active_flutter_project,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.dev.wizard_prefs import (
    load_workspace_prefs,
    save_workspace_prefs,
    workspace_prefs_path,
)


def _flutter_app(root: Path, name: str) -> Path:
    app = root / name
    app.mkdir(parents=True)
    (app / "pubspec.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    return app


def test_discover_flutter_projects_lists_immediate_children(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    alpha = _flutter_app(workspace, "alpha_app")
    beta = _flutter_app(workspace, "beta_app")

    assert discover_flutter_projects(workspace) == [alpha.resolve(), beta.resolve()]


def test_discover_flutter_projects_single_root_layout(tmp_path: Path) -> None:
    project = tmp_path / "solo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: solo\n", encoding="utf-8")

    assert discover_flutter_projects(project) == [project.resolve()]


def test_resolve_active_flutter_project_uses_workspace_prefs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    demo = _flutter_app(workspace, "demo_app")
    _flutter_app(workspace, "other_app")

    save_workspace_prefs(workspace, active_project="demo_app")
    assert resolve_active_flutter_project(env_workspace=workspace) == demo.resolve()


def test_resolve_active_flutter_project_ambiguous_without_prefs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _flutter_app(workspace, "one")
    _flutter_app(workspace, "two")

    assert resolve_active_flutter_project(env_workspace=workspace) is None


def test_resolve_active_flutter_project_auto_picks_single_child(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    only = _flutter_app(workspace, "only_app")

    assert resolve_active_flutter_project(env_workspace=workspace) == only.resolve()


def test_default_flutter_project_candidate_prefers_persisted_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    picked = _flutter_app(workspace, "picked_app")
    _flutter_app(workspace, "other_app")
    save_workspace_prefs(workspace, active_project="picked_app")

    monkeypatch.setattr(
        "figma_flutter_agent.dev.project._agent_repo_root",
        lambda: tmp_path / "agent_repo",
    )
    (tmp_path / "agent_repo").mkdir(exist_ok=True)

    assert default_flutter_project_candidate(env_project_dir=workspace) == picked.resolve()


def test_workspace_prefs_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    save_workspace_prefs(workspace, active_project="demo_app")
    assert load_workspace_prefs(workspace).active_project == "demo_app"
    assert workspace_prefs_path(workspace).is_file()


def test_active_project_relative_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project = _flutter_app(workspace, "demo_app")
    assert active_project_relative_path(workspace, project) == "demo_app"


def test_resolve_active_flutter_project_honors_prefs_without_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bare = _flutter_app(workspace, "demo_app2")
    _flutter_app(workspace, "demo_app")

    save_workspace_prefs(workspace, active_project="demo_app2")
    assert resolve_active_flutter_project(env_workspace=workspace) == bare.resolve()


def test_ensure_batch_manifest_creates_empty_yaml(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    primary = _flutter_app(workspace, "demo_app")
    secondary = _flutter_app(workspace, "demo_app2")
    (primary / "screens.yaml").write_text(
        "file_key: ABC123XYZ\nproject_dir: .\nscreens: []\n",
        encoding="utf-8",
    )

    path = ensure_batch_manifest(secondary, workspace_root=workspace)
    assert path == secondary / "screens.yaml"
    assert has_batch_manifest(secondary)
    text = path.read_text(encoding="utf-8")
    assert "file_key: ABC123XYZ" in text
    assert "screens: []" in text


def test_ensure_batch_manifest_raises_without_file_key_source(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    lonely = _flutter_app(workspace, "solo")

    assert infer_figma_file_key_for_manifest(workspace_root=workspace) is None
    with pytest.raises(FlutterProjectError, match="Cannot create screens.yaml"):
        ensure_batch_manifest(lonely, workspace_root=workspace)
