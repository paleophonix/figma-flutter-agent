"""Wizard preview capture must use browser preview, not warm Flutter sandbox."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.view_renders import run_view_preview_capture
from figma_flutter_agent.preview.models import PreviewCaptureResult, PreviewScene
from figma_flutter_agent.schemas.tree import CleanDesignTreeNode


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Frame",
        type="CONTAINER",
        sizing={"width": 100, "height": 100},
        children=[],
    )


def test_wizard_preview_does_not_call_warm_flutter_capture(tmp_path: Path) -> None:
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    bundle_path = tmp_path / "bundle.dart"
    bundle_path.write_text("// bundle", encoding="utf-8")
    settings = Settings()

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("capture_planned_in_warm_sandbox must not run in preview mode")

    scene = PreviewScene(width=100, height=100, nodes=[])
    fake_png = b"\x89PNG\r\n\x1a\n"

    with (
        patch(
            "figma_flutter_agent.dev.view_renders.load_clean_tree_from_debug",
            return_value=_minimal_tree(),
        ),
        patch(
            "figma_flutter_agent.dev.warm_capture.capture_planned_in_warm_sandbox",
            side_effect=_forbidden,
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.preview_scene_from_clean_tree",
            return_value=scene,
        ) as build_scene,
        patch(
            "figma_flutter_agent.dev.view_renders.capture_preview_png",
            return_value=PreviewCaptureResult(png=fake_png, backend="browser_preview"),
        ) as capture_preview,
        patch(
            "figma_flutter_agent.dev.view_renders.persist_latest_screen_capture",
            return_value=tmp_path / "screen",
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.debug_capture_artifact_path",
            return_value=tmp_path / "preview_capture.png",
        ),
    ):
        output = run_view_preview_capture(
            project_dir,
            feature_name="login",
            bundle_path=bundle_path,
            settings=settings,
        )

    build_scene.assert_called_once()
    capture_preview.assert_called_once()
    assert output == tmp_path / "preview_capture.png"


def test_wizard_preview_persists_flat_preview_capture(tmp_path: Path) -> None:
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    bundle_path = tmp_path / "bundle.dart"
    bundle_path.write_text("// bundle", encoding="utf-8")
    settings = Settings()
    scene = PreviewScene(width=100, height=100, nodes=[])
    persist_mock = MagicMock()

    with (
        patch(
            "figma_flutter_agent.dev.view_renders.load_clean_tree_from_debug",
            return_value=_minimal_tree(),
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.preview_scene_from_clean_tree",
            return_value=scene,
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.capture_preview_png",
            return_value=PreviewCaptureResult(png=b"png", backend="browser_preview"),
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.persist_latest_screen_capture",
            persist_mock,
        ),
        patch(
            "figma_flutter_agent.dev.view_renders.debug_capture_artifact_path",
            return_value=tmp_path / "preview_capture.png",
        ),
    ):
        run_view_preview_capture(
            project_dir,
            feature_name="login",
            bundle_path=bundle_path,
            settings=settings,
        )

    persist_mock.assert_called_once()
    assert persist_mock.call_args.kwargs["use_preview_artifact"] is True
    assert persist_mock.call_args.kwargs["capture_png"] == b"png"
