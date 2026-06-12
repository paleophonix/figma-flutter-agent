"""Fixture capture batch reuses warm sandbox across screens."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.warm_capture import warm_capture_sandbox_dir
from figma_flutter_agent.validation.golden_capture import (
    FixtureCaptureBatch,
    GoldenCaptureResult,
)


@patch("figma_flutter_agent.dev.warm_capture.capture_planned_in_warm_sandbox")
def test_batch_reuses_one_sandbox_dir_for_multiple_features(
    warm_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    warm_mock.return_value = GoldenCaptureResult(png=b"png")
    batch = FixtureCaptureBatch(
        settings=Settings(),
        project_dir=project,
        write_timings=False,
    )
    batch.golden_runtime = "host"

    planned = {"test/capture/foo_screen_capture_test.dart": "//"}
    for feature in ("alpha", "beta"):
        batch.capture_planned(planned, feature_name=feature, layout_tree=None)

    assert warm_mock.call_count == 2
    for call in warm_mock.call_args_list:
        assert call.kwargs["project_dir"] == project
    sandbox = warm_capture_sandbox_dir(project)
    assert sandbox.name == "sandbox"
    assert sandbox.parent.name == "capture"


@patch("figma_flutter_agent.dev.warm_capture._run_flutter_pub_get", return_value=None)
@patch("figma_flutter_agent.dev.warm_capture._copy_skeleton_project")
@patch("figma_flutter_agent.dev.warm_capture.capture_planned_flutter_golden_png")
def test_warm_session_pub_get_validated_when_sandbox_exists(
    capture_mock: MagicMock,
    copy_mock: MagicMock,
    pub_mock: MagicMock,
    tmp_path: Path,
) -> None:
    from figma_flutter_agent.dev import warm_capture as warm_mod
    from figma_flutter_agent.validation.golden_capture.project import (
        _write_skeleton_fingerprint_stamp,
    )

    project = tmp_path / "demo"
    project.mkdir()
    sandbox = warm_capture_sandbox_dir(project)
    sandbox.mkdir(parents=True)
    (sandbox / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")
    _write_skeleton_fingerprint_stamp(sandbox)
    warm_mod._WARM_SESSIONS.clear()
    capture_mock.return_value = GoldenCaptureResult(png=b"png")

    warm_mod.capture_planned_in_warm_sandbox(
        {"test/capture/a_screen_capture_test.dart": "//"},
        feature_name="alpha",
        project_dir=project,
        layout_tree=None,
        settings=None,
    )

    copy_mock.assert_not_called()
    pub_mock.assert_called_once()


@patch("figma_flutter_agent.dev.warm_capture._run_flutter_pub_get", return_value=None)
@patch("figma_flutter_agent.dev.warm_capture._copy_skeleton_project")
@patch("figma_flutter_agent.dev.warm_capture.capture_planned_flutter_golden_png")
def test_warm_session_bootstrap_once_per_project(
    capture_mock: MagicMock,
    copy_mock: MagicMock,
    _pub_mock: MagicMock,
    tmp_path: Path,
) -> None:
    from figma_flutter_agent.dev import warm_capture as warm_mod

    project = tmp_path / "demo"
    project.mkdir()
    warm_mod._WARM_SESSIONS.clear()

    from figma_flutter_agent.validation.golden_capture.project import (
        _write_skeleton_fingerprint_stamp,
    )

    def _materialize_skeleton(target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "pubspec.yaml").write_text("name: warm\n", encoding="utf-8")
        _write_skeleton_fingerprint_stamp(target)

    copy_mock.side_effect = _materialize_skeleton
    capture_mock.return_value = GoldenCaptureResult(png=b"png")

    planned = {"test/capture/a_screen_capture_test.dart": "//"}
    warm_mod.capture_planned_in_warm_sandbox(
        planned,
        feature_name="alpha",
        project_dir=project,
        layout_tree=None,
        settings=None,
    )
    warm_mod.capture_planned_in_warm_sandbox(
        planned,
        feature_name="beta",
        project_dir=project,
        layout_tree=None,
        settings=None,
    )

    assert copy_mock.call_count == 1
