"""Tests for Chrome artboard preview window sizing."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from figma_flutter_agent.config.models import ResponsiveConfig
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.preview_size import (
    ARTBOARD_PREVIEW_HEIGHT_DEFINE,
    ARTBOARD_PREVIEW_WIDTH_DEFINE,
    chrome_live_launch_flags,
    chrome_preview_dart_defines,
    chrome_preview_launch_flags,
    chrome_preview_window_flags,
    chrome_web_run_flags,
    infer_artboard_size_from_dump,
    is_chrome_device,
    prepare_artboard_chrome_launch,
    responsive_config_preview_size,
)
from figma_flutter_agent.dev.run import launch_flutter_app


@contextmanager
def _patch_launch_recording(
    calls: list[list[str]],
    *,
    background_calls: list[list[str]] | None = None,
) -> Iterator[None]:
    """Record ``flutter run`` argv while skipping real subprocess I/O."""

    def _record_interactive(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(list(command), 0)

    def _record_background(run_cmd: list[str], **kwargs: object) -> MagicMock:
        sink = background_calls if background_calls is not None else calls
        sink.append(list(run_cmd))
        proc = MagicMock()
        proc.poll.return_value = None
        return proc

    with (
        patch(
            "figma_flutter_agent.dev.flutter_launch.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.flutter_launch.reap_stale_flutter_web_processes",
            return_value=0,
        ),
        patch("figma_flutter_agent.dev.flutter_launch.run_flutter_command"),
        patch(
            "figma_flutter_agent.dev.flutter_launch.run_interactive_subprocess",
            side_effect=_record_interactive,
        ),
        patch(
            "figma_flutter_agent.dev.flutter_launch._spawn_flutter_run_background",
            side_effect=_record_background,
        ),
    ):
        yield


def test_responsive_config_legacy_enabled_migration() -> None:
    assert ResponsiveConfig.model_validate({"enabled": True}).mode == "responsive"
    assert ResponsiveConfig.model_validate({"enabled": False}).mode == "static"
    assert ResponsiveConfig(mode="both").enabled is True
    assert ResponsiveConfig(mode="static").enabled is False


def test_responsive_config_preview_size_returns_pair() -> None:
    responsive = ResponsiveConfig(preview_width=428, preview_height=926)
    assert responsive_config_preview_size(responsive) == (428, 926)


def test_responsive_config_preview_size_none_when_unset() -> None:
    assert responsive_config_preview_size(ResponsiveConfig()) is None


def test_responsive_config_preview_size_requires_both_dimensions() -> None:
    with pytest.raises(ValidationError, match="preview_width and responsive.preview_height"):
        ResponsiveConfig(preview_width=390)


def test_infer_artboard_size_from_raw_dump(tmp_path: Path) -> None:
    dump = tmp_path / "screen.json"
    dump.write_text(
        json.dumps(
            {
                "id": "1:1",
                "type": "FRAME",
                "absoluteBoundingBox": {"width": 390.0, "height": 844.0},
            }
        ),
        encoding="utf-8",
    )
    assert infer_artboard_size_from_dump(dump) == (390, 844)


def test_infer_artboard_size_from_processed_dump(tmp_path: Path) -> None:
    dump = tmp_path / "processed.json"
    dump.write_text(
        json.dumps(
            {
                "cleanTree": {
                    "sizing": {"width": 393.0, "height": 852.0},
                }
            }
        ),
        encoding="utf-8",
    )
    assert infer_artboard_size_from_dump(dump) == (393, 852)


def test_chrome_preview_window_flags() -> None:
    flags = chrome_preview_window_flags(390, 844)
    assert "--web-browser-flag=--hide-scrollbars" in flags
    joined = " ".join(flags)
    assert "--window-size=" not in joined
    assert "--window-position=" not in joined


def test_chrome_preview_window_flags_can_skip_window_size() -> None:
    flags = chrome_preview_window_flags(390, 844, set_window_size=False)
    assert "--window-size=" not in " ".join(flags)


def test_chrome_web_run_flags_disable_cdn() -> None:
    assert chrome_web_run_flags() == ["--no-web-resources-cdn"]


def test_chrome_preview_dart_defines() -> None:
    assert chrome_preview_dart_defines(390, 844) == [
        f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390",
        f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}=844",
    ]


def test_chrome_preview_launch_flags_includes_dart_defines() -> None:
    flags = chrome_preview_launch_flags(390, 844)
    assert f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390" in flags
    assert "--web-browser-flag=--hide-scrollbars" in flags


def test_chrome_live_launch_flags_pass_artboard_dart_defines() -> None:
    flags = chrome_live_launch_flags(390, 844)
    assert f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390" in flags
    assert f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}=844" in flags
    assert "--web-browser-flag=--hide-scrollbars" in flags
    assert "--web-browser-flag=--start-maximized" not in " ".join(flags)


def test_is_chrome_device() -> None:
    assert is_chrome_device("chrome")
    assert is_chrome_device("edge")
    assert not is_chrome_device("windows")
    assert not is_chrome_device(None)


def test_prepare_artboard_chrome_launch_infers_dump_and_defaults_chrome(
    tmp_path: Path,
) -> None:
    dump = tmp_path / "screen.json"
    dump.write_text(
        json.dumps(
            {
                "absoluteBoundingBox": {"width": 390.0, "height": 844.0},
            }
        ),
        encoding="utf-8",
    )
    with patch(
        "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
        return_value="chrome",
    ):
        device_id, preview_size = prepare_artboard_chrome_launch(
            device_id=None,
            flutter_sdk=None,
            dump_path=dump,
        )
    assert device_id == "chrome"
    assert preview_size == (390, 844)


def test_launch_flutter_app_passes_chrome_window_flags(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    calls: list[list[str]] = []

    with _patch_launch_recording(calls):
        launch_flutter_app(
            project,
            device_id="chrome",
            preview_size=(390, 844),
            artboard_preview=True,
        )

    run_cmd = calls[0]
    assert run_cmd[:5] == ["flutter", "run", "--no-pub", "-d", "chrome"]
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH=390" in run_cmd
    assert "--web-browser-flag=--hide-scrollbars" in run_cmd
    assert "--window-size=" not in " ".join(run_cmd)


def test_launch_flutter_app_live_mode_passes_artboard_dart_defines(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    calls: list[list[str]] = []

    with _patch_launch_recording(calls):
        launch_flutter_app(project, device_id="chrome", preview_size=(390, 844))

    run_cmd = calls[0]
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH=390" in run_cmd
    assert "--web-browser-flag=--hide-scrollbars" in run_cmd


def test_launch_flutter_app_uses_dump_path_for_wizard_defaults(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    dump = tmp_path / "screen.json"
    dump.write_text(
        json.dumps(
            {
                "absoluteBoundingBox": {"width": 390.0, "height": 844.0},
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    with (
        _patch_launch_recording(calls),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, dump_path=dump)

    run_cmd = calls[0]
    assert run_cmd[:5] == ["flutter", "run", "--no-pub", "-d", "chrome"]
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH=390" in run_cmd
    assert "--window-size=" not in " ".join(run_cmd)


def test_launch_flutter_app_prefers_dump_artboard_size_over_config_preview_size(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    dump = tmp_path / "screen.json"
    dump.write_text(
        json.dumps(
            {
                "absoluteBoundingBox": {"width": 390.0, "height": 844.0},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings().model_copy(
        update={
            "agent": Settings().agent.model_copy(
                update={
                    "responsive": ResponsiveConfig(
                        preview_width=428,
                        preview_height=926,
                    )
                }
            )
        }
    )
    calls: list[list[str]] = []

    with (
        _patch_launch_recording(calls),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, dump_path=dump, settings=settings)

    joined = " ".join(calls[0])
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in joined
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT" not in joined
    assert "--window-size=" not in joined


def test_launch_flutter_app_uses_config_preview_size_when_dump_missing(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    settings = Settings().model_copy(
        update={
            "agent": Settings().agent.model_copy(
                update={
                    "responsive": ResponsiveConfig(
                        preview_width=428,
                        preview_height=926,
                    )
                }
            )
        }
    )
    calls: list[list[str]] = []

    with (
        _patch_launch_recording(calls),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, settings=settings)

    joined = " ".join(calls[0])
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in joined
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT" not in joined
    assert "--window-size=" not in joined


def test_launch_flutter_app_responsive_enabled_skips_artboard_defines(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    settings = Settings().model_copy(
        update={
            "agent": Settings().agent.model_copy(
                update={
                    "responsive": ResponsiveConfig(
                        mode="responsive",
                        max_web_width=1200,
                        preview_width=390,
                        preview_height=844,
                    ),
                },
            ),
        },
    )
    calls: list[list[str]] = []

    with _patch_launch_recording(calls):
        launch_flutter_app(
            project,
            device_id="chrome",
            preview_size=(390, 844),
            settings=settings,
        )

    joined = " ".join(calls[0])
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in joined
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT" not in joined
    assert "--window-size=" not in joined


def test_launch_flutter_app_static_mode_uses_artboard_defines(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    dump = tmp_path / "screen.json"
    dump.write_text(
        json.dumps(
            {
                "absoluteBoundingBox": {"width": 390.0, "height": 844.0},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings().model_copy(
        update={
            "agent": Settings().agent.model_copy(
                update={
                    "responsive": ResponsiveConfig(
                        mode="static",
                        max_web_width=1200,
                    ),
                },
            ),
        },
    )
    calls: list[list[str]] = []

    with (
        _patch_launch_recording(calls),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, dump_path=dump, settings=settings)

    joined = " ".join(calls[0])
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH=390" in joined
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT=844" in joined
    assert "--window-size=" not in joined


def test_launch_flutter_app_both_mode_spawns_dual_windows(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    settings = Settings().model_copy(
        update={
            "agent": Settings().agent.model_copy(
                update={
                    "responsive": ResponsiveConfig(
                        mode="both",
                        preview_width=390,
                        preview_height=844,
                    ),
                },
            ),
        },
    )
    foreground_calls: list[list[str]] = []
    background_calls: list[list[str]] = []

    with (
        _patch_launch_recording(
            foreground_calls,
            background_calls=background_calls,
        ),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, settings=settings)

    assert len(background_calls) == 1
    assert len(foreground_calls) == 1
    static_joined = " ".join(background_calls[0])
    responsive_joined = " ".join(foreground_calls[0])
    assert "--web-port 7357" in static_joined
    assert "--web-port 7358" in responsive_joined
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" in static_joined
    assert "FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in responsive_joined
    assert "--web-browser-flag=--window-position=406,0" in responsive_joined
