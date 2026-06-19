"""Tests for debug context bundle collection."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.debug.context import collect_screen_debug_context
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.errors import FigmaFlutterError


@pytest.fixture
def agent_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "agent_repo"
    root.mkdir()
    monkeypatch.setattr(
        "figma_flutter_agent.debug.paths.agent_repo_root",
        lambda: root,
    )
    return root


def test_collect_screen_debug_context_uses_screen_root(agent_root: Path) -> None:
    project = Path("/proj/demo_app")
    feature = "login_v1"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "last.log").write_text("line1\nline2\n", encoding="utf-8")

    bundle = collect_screen_debug_context(project, feature)

    assert bundle.screen_root == root
    assert bundle.feature == feature
    assert "processed.json" in bundle.present_files
    assert "last.log" in bundle.present_files
    assert "line2" in bundle.log_tail


def test_collect_screen_debug_context_requires_minimum_artifacts(agent_root: Path) -> None:
    project = Path("/proj/demo_app")
    feature = "empty_screen"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "figma.png").write_bytes(b"png")

    with pytest.raises(FigmaFlutterError, match="processed.json or last.log"):
        collect_screen_debug_context(project, feature)


def test_collect_screen_debug_context_missing_root(agent_root: Path) -> None:
    project = Path("/proj/demo_app")

    with pytest.raises(FigmaFlutterError, match="Debug bundle missing"):
        collect_screen_debug_context(project, "missing")
