"""Warm capture sandbox session reuse."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from figma_flutter_agent.dev.warm_capture import (
    capture_planned_in_warm_sandbox,
    get_or_create_warm_session,
    reset_warm_capture_session,
    warm_capture_sandbox_dir,
)
from figma_flutter_agent.validation.golden_capture import (
    GoldenCaptureHostSession,
    GoldenCaptureResult,
)


def test_warm_capture_sandbox_dir_under_agent_debug(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    sandbox = warm_capture_sandbox_dir(project)
    assert sandbox.name == ".sandbox"


def test_reset_warm_capture_session_closes_cached_session(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    session = MagicMock(spec=GoldenCaptureHostSession)
    key = (project.resolve().as_posix(), "background")
    import figma_flutter_agent.dev.warm_capture as warm_mod

    warm_mod._WARM_SESSIONS[key] = session
    reset_warm_capture_session(project, "background")
    session.close.assert_called_once()
    assert key not in warm_mod._WARM_SESSIONS


def test_get_or_create_warm_session_returns_cached_instance(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    cached = MagicMock(spec=GoldenCaptureHostSession)
    cached.capture_dir = warm_capture_sandbox_dir(project)
    key = (project.resolve().as_posix(), "music")
    import figma_flutter_agent.dev.warm_capture as warm_mod

    warm_mod._WARM_SESSIONS[key] = cached
    result = get_or_create_warm_session(project, "music", {}, None)
    assert result is cached


@patch("figma_flutter_agent.dev.warm_capture.capture_planned_flutter_golden_png")
@patch("figma_flutter_agent.dev.warm_capture.get_or_create_warm_session")
def test_capture_planned_in_warm_sandbox_uses_sandbox_capture(
    session_mock: MagicMock,
    capture_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    session = MagicMock(spec=GoldenCaptureHostSession)
    session_mock.return_value = session
    capture_mock.return_value = GoldenCaptureResult(png=b"png")

    planned = {"test/capture/foo_screen_capture_test.dart": "// test"}
    result = capture_planned_in_warm_sandbox(
        planned,
        feature_name="foo",
        project_dir=project,
        layout_tree=None,
        settings=None,
    )

    assert result.png == b"png"
    capture_mock.assert_called_once()
    _, kwargs = capture_mock.call_args
    assert kwargs["host_session"] is session
    assert kwargs["capture_in_project"] is False
    assert kwargs["golden_runtime"] == "host"
    assert kwargs["no_docker"] is True


@patch("figma_flutter_agent.dev.warm_capture.capture_planned_flutter_golden_png")
@patch("figma_flutter_agent.dev.warm_capture.get_or_create_warm_session")
def test_capture_planned_in_warm_sandbox_forwards_timings(
    session_mock: MagicMock,
    capture_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    session = MagicMock(spec=GoldenCaptureHostSession)
    session_mock.return_value = session
    capture_mock.return_value = GoldenCaptureResult(png=b"png")
    from figma_flutter_agent.validation.golden_capture import GoldenCaptureTimings

    timings = GoldenCaptureTimings(feature="foo")
    capture_planned_in_warm_sandbox(
        {},
        feature_name="foo",
        project_dir=project,
        layout_tree=None,
        settings=None,
        timings=timings,
    )
    session_mock.assert_called_once()
    assert session_mock.call_args.kwargs["timings"] is timings
    assert capture_mock.call_args.kwargs["timings"] is timings


@patch("figma_flutter_agent.dev.warm_capture.get_or_create_warm_session")
def test_capture_planned_in_warm_sandbox_propagates_bootstrap_failure(
    session_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    session_mock.return_value = GoldenCaptureResult(reason="pub get failed")

    result = capture_planned_in_warm_sandbox(
        {},
        feature_name="foo",
        project_dir=project,
        layout_tree=None,
        settings=None,
    )

    assert not result.ok
    assert result.reason == "pub get failed"
