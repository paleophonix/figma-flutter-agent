"""Tests for deprecated figma-debug mirror helpers and agent-log migration."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.migrate import migrate_agent_logs_into_project
from figma_flutter_agent.debug.mirror import (
    mirror_figma_debug_artifact,
    project_mirror_label,
    sync_figma_debug_tree,
)
from figma_flutter_agent.debug.paths import render_session_dir


def test_mirror_figma_debug_artifact_is_noop(tmp_path: Path) -> None:
    project = tmp_path / "demo_app"
    artifact = project / ".debug" / "raw" / "sign_in_layout.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    assert mirror_figma_debug_artifact(project, artifact) is None


def test_sync_figma_debug_tree_is_noop(tmp_path: Path) -> None:
    project = tmp_path / "demo_app"
    (project / ".debug" / "ir").mkdir(parents=True)
    (project / ".debug" / "ir" / "x.json").write_text("{}", encoding="utf-8")
    assert sync_figma_debug_tree(project) == []


def test_migrate_agent_logs_moves_mirror_dart_errors_and_renders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_root = tmp_path / "agent"
    agent_root.mkdir()
    monkeypatch.setattr(
        "figma_flutter_agent.debug.migrate.agent_repo_root",
        lambda: agent_root,
    )

    project = tmp_path / "apps" / "limbo"
    project.mkdir(parents=True)
    project_resolved = project.resolve().as_posix()

    label = project_mirror_label(project)
    mirror_ir = agent_root / "logs" / "figma-debug" / label / "ir" / "login.json"
    mirror_ir.parent.mkdir(parents=True)
    mirror_ir.write_text('{"stage":"pre"}', encoding="utf-8")

    dart_log = agent_root / "logs" / "dart-errors" / "2026-01-01T00-00-00Z-run1.jsonl"
    dart_log.parent.mkdir(parents=True)
    dart_log.write_text(
        json.dumps({"projectDir": project_resolved, "stage": "write"}) + "\n",
        encoding="utf-8",
    )

    render_session = agent_root / "logs" / "renders" / "2026-01-01T00-00-00Z-run2"
    render_session.mkdir(parents=True)
    (render_session / "flutter_render.png").write_bytes(b"png")
    (render_session / "manifest.jsonl").write_text(
        json.dumps({"projectDir": project_resolved, "label": "flutter_render"}) + "\n",
        encoding="utf-8",
    )

    moved = migrate_agent_logs_into_project(project)
    assert moved == 4
    assert (project / ".debug" / "ir" / "login.json").is_file()
    assert (project / ".debug" / "logs" / "last.log").is_file()
    assert (render_session_dir(project, render_session.name) / "flutter_render.png").is_file()
    assert not mirror_ir.is_file()
    assert not dart_log.is_file()
    assert not render_session.exists()
