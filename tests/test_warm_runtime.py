"""Warm capture runtime routing and perf schema tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.validation.golden_capture import (
    FixtureCaptureBatch,
    GoldenCaptureResult,
    GoldenCaptureTimings,
    capture_planned_for_fixture,
    persist_golden_capture_timings,
    resolve_local_capture_mode,
)
from figma_flutter_agent.validation.golden_capture.project import (
    _compute_pubspec_cache_key,
    _pubspec_cache_stamp,
    _run_flutter_pub_get,
)


def test_golden_capture_timings_json_schema() -> None:
    timings = GoldenCaptureTimings(
        feature="music_v2",
        mode="host_sandbox",
        workspace="sandbox",
        fast_capture=True,
    )
    timings.add("flutterTest", 12.0)
    timings.add("pubGet", 0.0)
    payload = timings.to_json()
    assert payload["feature"] == "music_v2"
    assert payload["mode"] == "host_sandbox"
    assert payload["fastCapture"] is True
    assert payload["workspace"] == "sandbox"
    assert payload["timingsSec"]["flutterTest"] == 12.0
    assert payload["timingsSec"]["pubGet"] == 0.0


def test_resolve_local_capture_mode_prefers_host_when_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIGMA_GOLDEN_RUNTIME", raising=False)
    settings = Settings()
    selection = resolve_local_capture_mode(settings=settings)
    assert selection.runtime == "host"
    assert selection.configured == "auto"


def test_resolve_local_capture_mode_respects_explicit_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIGMA_GOLDEN_RUNTIME", "docker")
    settings = Settings()
    with patch(
        "figma_flutter_agent.validation.golden_runtime.docker_cli_available",
        return_value=True,
    ):
        selection = resolve_local_capture_mode(settings=settings)
    assert selection.runtime == "docker"


@patch("figma_flutter_agent.dev.warm_capture.capture_planned_in_warm_sandbox")
def test_capture_planned_for_fixture_routes_warm_sandbox(
    warm_mock: MagicMock,
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    warm_mock.return_value = GoldenCaptureResult(png=b"png", timings=GoldenCaptureTimings())
    batch = FixtureCaptureBatch(settings=Settings(), project_dir=project)
    batch.golden_runtime = "host"
    result = capture_planned_for_fixture(
        batch,
        {"test/capture/foo_screen_capture_test.dart": "//"},
        feature_name="foo",
        layout_tree=None,
    )
    assert result.png == b"png"
    warm_mock.assert_called_once()
    assert warm_mock.call_args.kwargs["project_dir"] == project


@patch("figma_flutter_agent.validation.golden_capture.warm_runtime.capture_planned_flutter_golden_png")
def test_capture_planned_for_fixture_routes_docker_without_warm(
    capture_mock: MagicMock,
) -> None:
    capture_mock.return_value = GoldenCaptureResult(png=b"cold")
    batch = FixtureCaptureBatch(settings=Settings(), project_dir=None)
    batch.golden_runtime = "docker"
    result = capture_planned_for_fixture(
        batch,
        {"test/golden/foo_screen_golden_test.dart": "//"},
        feature_name="foo",
        layout_tree=None,
    )
    assert result.png == b"cold"
    capture_mock.assert_called_once()
    assert capture_mock.call_args.kwargs["golden_runtime"] == "docker"


def test_pub_get_skipped_when_stamp_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "proj"
    workspace.mkdir()
    (workspace / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    stamp = _pubspec_cache_stamp(workspace)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(_compute_pubspec_cache_key(workspace, "flutter"), encoding="utf-8")

    with patch("figma_flutter_agent.generator.codegen.run_pub_get") as pub_mock:
        failure = _run_flutter_pub_get(workspace, "flutter")
    assert failure is None
    pub_mock.assert_not_called()


def test_persist_golden_capture_timings_writes_project_only_when_project_bound(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    agent_perf = tmp_path / "agent_perf"
    timings = GoldenCaptureTimings(feature="music_v2", screen_id="music_v2_ru_dirty")
    timings.add("flutterTest", 2.0)
    persist_golden_capture_timings(
        timings,
        agent_timings_dir=agent_perf,
        project_dir=project,
    )
    assert not (agent_perf / "golden_capture_music_v2_ru_dirty.json").exists()
    assert (project / ".debug" / "perf" / "golden_capture_music_v2_ru_dirty.json").is_file()


def test_persist_golden_capture_timings_writes_agent_when_no_project(tmp_path: Path) -> None:
    agent_perf = tmp_path / "agent_perf"
    timings = GoldenCaptureTimings(feature="music_v2", screen_id="music_v2")
    timings.add("flutterTest", 1.0)
    persist_golden_capture_timings(timings, agent_timings_dir=agent_perf, project_dir=None)
    assert (agent_perf / "golden_capture_music_v2.json").is_file()


def test_persist_golden_capture_timings_distinct_project_paths_for_shared_feature(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    agent_perf = tmp_path / "agent_perf"
    for screen_id in ("music_v2", "music_v2_ru_dirty"):
        timings = GoldenCaptureTimings(feature="music_v2", screen_id=screen_id)
        persist_golden_capture_timings(
            timings,
            agent_timings_dir=agent_perf,
            project_dir=project,
        )
    perf_dir = project / ".debug" / "perf"
    assert (perf_dir / "golden_capture_music_v2.json").is_file()
    assert (perf_dir / "golden_capture_music_v2_ru_dirty.json").is_file()


def test_fixture_batch_writes_timings_json(tmp_path: Path) -> None:
    timings = GoldenCaptureTimings(
        feature="music_v2",
        screen_id="music_v2_ru_dirty",
        mode="host_sandbox",
    )
    timings.add("flutterTest", 1.5)
    project = tmp_path / "demo"
    project.mkdir()
    batch = FixtureCaptureBatch(
        settings=Settings(),
        project_dir=project,
        timings_dir=tmp_path / "perf",
        write_timings=True,
    )
    batch._persist_timings(timings)
    out_path = project / ".debug" / "perf" / "golden_capture_music_v2_ru_dirty.json"
    assert out_path.is_file()
    assert not (tmp_path / "perf" / "golden_capture_music_v2_ru_dirty.json").exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["feature"] == "music_v2"
    assert payload["screenId"] == "music_v2_ru_dirty"
    assert payload["timingsSec"]["flutterTest"] == 1.5


def test_fixture_batch_timings_env_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_GOLDEN_CAPTURE_TIMINGS", "1")
    batch = FixtureCaptureBatch(settings=Settings(), project_dir=tmp_path, write_timings=False)
    assert batch.write_timings is True
