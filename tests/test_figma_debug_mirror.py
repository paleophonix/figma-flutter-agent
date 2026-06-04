"""Tests for mirroring ``.figma_debug`` into ``logs/figma-debug``."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.dumps import write_raw_dump
from figma_flutter_agent.debug.mirror import (
    figma_debug_log_root,
    mirror_figma_debug_artifact,
    project_mirror_label,
    sync_figma_debug_tree,
)


def test_mirror_copies_under_logs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_root = tmp_path / "agent"
    agent_root.mkdir()
    monkeypatch.setattr(
        "figma_flutter_agent.debug.mirror.agent_repo_root",
        lambda: agent_root,
    )

    project = tmp_path / "demo_app"
    write_raw_dump(project, "background", {"id": "1:1", "type": "FRAME"})

    dest = mirror_figma_debug_artifact(
        project,
        project / ".figma_debug" / "raw" / "background_layout.json",
    )
    assert dest is not None
    assert dest.is_file()
    assert dest.parent.parent.parent == figma_debug_log_root()
    assert project_mirror_label(project) in dest.parts


def test_sync_tree_copies_all_subfolders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_root = tmp_path / "agent"
    agent_root.mkdir()
    monkeypatch.setattr(
        "figma_flutter_agent.debug.mirror.agent_repo_root",
        lambda: agent_root,
    )

    project = tmp_path / "demo_app"
    ir_dir = project / ".figma_debug" / "ir"
    ir_dir.mkdir(parents=True)
    (ir_dir / "background_pre_emit.json").write_text("{}", encoding="utf-8")
    reports = project / ".figma_debug" / "reports"
    reports.mkdir(parents=True)
    (reports / "background_design_coverage.json").write_text("{}", encoding="utf-8")

    copied = sync_figma_debug_tree(project)
    assert len(copied) == 2
    label = project_mirror_label(project)
    assert (figma_debug_log_root() / label / "ir" / "background_pre_emit.json").is_file()
