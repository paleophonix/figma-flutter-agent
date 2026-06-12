"""Runtime geometry capture routes through warm fixture runtime."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from figma_flutter_agent.config import Settings
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.stages.runtime_geometry_check import evaluate_runtime_geometry
from figma_flutter_agent.validation.golden_capture import GoldenCaptureResult


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
    )


@patch("figma_flutter_agent.stages.runtime_geometry_check.persist_golden_capture_timings")
@patch("figma_flutter_agent.stages.runtime_geometry_check.capture_planned_for_fixture")
def test_evaluate_runtime_geometry_uses_warm_capture_routing(
    capture_mock: MagicMock,
    persist_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    capture_mock.return_value = GoldenCaptureResult(
        figma_key_rects={"node": {"x": 0, "y": 0, "w": 10, "h": 10}},
    )
    settings = Settings()

    errors, feedback = evaluate_runtime_geometry(
        clean_tree=_minimal_tree(),
        planned_files={"test/capture/foo_screen_capture_test.dart": "//"},
        feature_name="foo",
        project_dir=project,
        settings=settings,
        min_iou=0.5,
        tier_thresholds=settings.agent.generation.geometry_tier_thresholds(),
        use_tier_thresholds=False,
        capture_if_missing=True,
    )

    capture_mock.assert_called_once()
    _, kwargs = capture_mock.call_args
    assert kwargs["project_dir"] == project
    assert kwargs["feature_name"] == "foo"
    persist_mock.assert_not_called()
    assert errors == []
    assert feedback == ""


@patch("figma_flutter_agent.stages.runtime_geometry_check.persist_golden_capture_timings")
@patch("figma_flutter_agent.stages.runtime_geometry_check.capture_planned_for_fixture")
def test_evaluate_runtime_geometry_persists_timings_when_present(
    capture_mock: MagicMock,
    persist_mock: MagicMock,
    tmp_path: Path,
) -> None:
    from figma_flutter_agent.validation.golden_capture import GoldenCaptureTimings

    project = tmp_path / "demo"
    project.mkdir()
    timings = GoldenCaptureTimings(feature="foo", mode="host_sandbox")
    capture_mock.return_value = GoldenCaptureResult(
        figma_key_rects={"node": {"x": 0, "y": 0, "w": 10, "h": 10}},
        timings=timings,
    )
    settings = Settings()

    evaluate_runtime_geometry(
        clean_tree=_minimal_tree(),
        planned_files={"test/capture/foo_screen_capture_test.dart": "//"},
        feature_name="foo",
        project_dir=project,
        settings=settings,
        min_iou=0.5,
        tier_thresholds=settings.agent.generation.geometry_tier_thresholds(),
        use_tier_thresholds=False,
        capture_if_missing=True,
    )

    persist_mock.assert_called_once_with(timings, project_dir=project)
