"""Unit tests for processed debug snapshot copy."""

from __future__ import annotations

from pathlib import Path

import pytest

from control_panel.repair.snapshot import (
    copy_processed_snapshot,
    read_debug_text,
    repair_debug_dest,
)


def test_repair_debug_dest_layout(tmp_path: Path) -> None:
    dest = repair_debug_dest(tmp_path, "demo_app", "login")
    assert dest == tmp_path / ".repair" / "debug" / "demo_app" / "login"


def test_copy_processed_snapshot_selects_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flutter = tmp_path / "demo_app"
    feature = "feedback"
    source = tmp_path / "agent_debug" / "demo_app" / feature
    source.mkdir(parents=True)
    (source / "processed.json").write_text('{"ok": true}', encoding="utf-8")
    (source / "dart-errors.json").write_text("[]", encoding="utf-8")
    (source / "last.log").write_text("x" * 50_000, encoding="utf-8")

    def fake_screen_root(project_dir: Path, slug: str) -> Path:
        assert slug == feature
        return source

    monkeypatch.setattr(
        "control_panel.repair.snapshot.screen_root",
        fake_screen_root,
    )
    worktree = tmp_path / "wt"
    worktree.mkdir()
    result = copy_processed_snapshot(
        flutter_project_dir=flutter,
        feature_slug=feature,
        worktree=worktree,
        project_slug="demo_app",
    )
    assert "processed.json" in result.copied_files
    assert "dart-errors.json" in result.copied_files
    assert "last.log" in result.copied_files
    assert (result.dest_debug_root / "processed.json").is_file()
    tail = read_debug_text(result.dest_debug_root, "last.log")
    assert len(tail) <= 32_000
