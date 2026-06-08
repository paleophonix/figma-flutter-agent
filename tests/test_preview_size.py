"""Tests for Chrome artboard preview window sizing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.dev.preview_size import (
    ARTBOARD_PREVIEW_HEIGHT_DEFINE,
    ARTBOARD_PREVIEW_WIDTH_DEFINE,
    chrome_live_launch_flags,
    chrome_preview_dart_defines,
    chrome_preview_launch_flags,
    chrome_preview_window_flags,
    infer_artboard_size_from_dump,
    is_chrome_device,
    prepare_artboard_chrome_launch,
)
from figma_flutter_agent.dev.run import launch_flutter_app


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
    assert "--web-browser-flag=--window-size=" not in " ".join(flags)
    assert "--web-browser-flag=--window-position=" not in " ".join(flags)
    assert "--web-browser-flag=--hide-scrollbars" in flags


def test_chrome_preview_dart_defines() -> None:
    assert chrome_preview_dart_defines(390, 844) == [
        f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390",
        f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}=844",
    ]


def test_chrome_preview_launch_flags_includes_dart_defines() -> None:
    flags = chrome_preview_launch_flags(390, 844)
    assert f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390" in flags
    assert "--web-browser-flag=--hide-scrollbars" in flags


def test_chrome_live_launch_flags_omit_dart_defines() -> None:
    flags = chrome_live_launch_flags(390, 844)
    assert "--dart-define=" not in " ".join(flags)
    assert "--web-browser-flag=--hide-scrollbars" in flags


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

    def _record(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    with (
        patch(
            "figma_flutter_agent.dev.flutter_launch.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.flutter_launch.reap_stale_flutter_web_processes",
            return_value=0,
        ),
        patch("figma_flutter_agent.dev.flutter_launch.subprocess.run", side_effect=_record),
    ):
        launch_flutter_app(
            project,
            device_id="chrome",
            preview_size=(390, 844),
            artboard_preview=True,
        )

    assert calls[1][:5] == ["flutter", "run", "--no-pub", "-d", "chrome"]
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH=390" in calls[1]
    assert "--web-browser-flag=--hide-scrollbars" in calls[1]
    assert "--web-browser-flag=--window-size=" not in " ".join(calls[1])


def test_launch_flutter_app_live_mode_omits_artboard_dart_defines(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    calls: list[list[str]] = []

    def _record(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    with (
        patch(
            "figma_flutter_agent.dev.flutter_launch.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.flutter_launch.reap_stale_flutter_web_processes",
            return_value=0,
        ),
        patch("figma_flutter_agent.dev.flutter_launch.subprocess.run", side_effect=_record),
    ):
        launch_flutter_app(project, device_id="chrome", preview_size=(390, 844))

    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in " ".join(calls[1])
    assert "--web-browser-flag=--hide-scrollbars" in calls[1]


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

    def _record(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    with (
        patch(
            "figma_flutter_agent.dev.flutter_launch.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.flutter_launch.reap_stale_flutter_web_processes",
            return_value=0,
        ),
        patch("figma_flutter_agent.dev.flutter_launch.subprocess.run", side_effect=_record),
        patch(
            "figma_flutter_agent.dev.preview_size.resolve_default_chrome_device_id",
            return_value="chrome",
        ),
    ):
        launch_flutter_app(project, dump_path=dump)

    assert calls[1][:5] == ["flutter", "run", "--no-pub", "-d", "chrome"]
    assert "--dart-define=FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH" not in " ".join(calls[1])
