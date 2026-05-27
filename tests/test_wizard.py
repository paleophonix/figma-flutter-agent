"""Tests for interactive wizard workflows."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.run import RunScreenPlan
from figma_flutter_agent.dev.wizard import (
    build_run_plan,
    collect_doctor_report,
    collect_screen_preflight,
    default_flutter_device_option,
    device_id_from_choice,
    format_screen_preflight,
    resolve_live_sync,
)


def _sample_plan(tmp_path: Path, *, dump_body: dict | None = None) -> RunScreenPlan:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
    dump_dir = project / ".figma_debug" / "raw"
    dump_dir.mkdir(parents=True)
    dump_path = dump_dir / "music_v2_layout.json"
    body = dump_body or {
        "id": "1:3978",
        "name": "music V2",
        "type": "FRAME",
        "children": [
            {"id": "1:3979", "name": "Vector", "type": "VECTOR", "visible": True},
            {"id": "1:3980", "name": "Vector", "type": "VECTOR", "visible": True},
        ],
    }
    dump_path.write_text(json.dumps(body), encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: music_v2",
                "    node_id: 1:3978",
                "    dump: .figma_debug/raw/music_v2_layout.json",
            ]
        ),
        encoding="utf-8",
    )
    example = Path(__file__).resolve().parents[1] / ".ai-figma-flutter.yml.example"
    if example.is_file():
        (project / ".ai-figma-flutter.yml").write_text(
            example.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return build_run_plan(project_dir=project, screen_name="music_v2")


def test_build_run_plan_without_existing_dump(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: music_v2",
                "    node_id: 1:3978",
            ]
        ),
        encoding="utf-8",
    )
    example = Path(__file__).resolve().parents[1] / ".ai-figma-flutter.yml.example"
    if example.is_file():
        (project / ".ai-figma-flutter.yml").write_text(
            example.read_text(encoding="utf-8"), encoding="utf-8"
        )
    plan = build_run_plan(project_dir=project, screen_name="music_v2")
    assert plan.screen.feature == "music_v2"
    assert not plan.dump_path.is_file()


def test_collect_screen_preflight_reports_missing_icons(tmp_path: Path) -> None:
    plan = _sample_plan(tmp_path)
    preflight = collect_screen_preflight(plan)
    assert preflight.dump_exists is True
    assert preflight.exportable_icons == 2
    assert preflight.local_icons == 0
    assert preflight.missing_asset_exports == 2
    assert preflight.needs_live_sync is True


def test_collect_screen_preflight_ignores_screen_frame_root(tmp_path: Path) -> None:
    plan = _sample_plan(
        tmp_path,
        dump_body={
            "id": "1:3978",
            "name": "music V2",
            "type": "FRAME",
            "exportSettings": [{"format": "SVG"}],
            "children": [
                {"id": "1:3979", "name": "Vector", "type": "VECTOR", "visible": True},
            ],
        },
    )
    icons_dir = plan.project_dir / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    (icons_dir / "vector_1_3979.svg").write_text("<svg/>", encoding="utf-8")
    preflight = collect_screen_preflight(plan)
    assert preflight.exportable_icons == 1
    assert preflight.missing_asset_exports == 0
    assert preflight.needs_live_sync is False


def test_collect_screen_preflight_complete_when_icons_on_disk(tmp_path: Path) -> None:
    plan = _sample_plan(tmp_path)
    icons_dir = plan.project_dir / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    (icons_dir / "vector_1_3979.svg").write_text("<svg/>", encoding="utf-8")
    (icons_dir / "vector_1_3980.svg").write_text("<svg/>", encoding="utf-8")
    preflight = collect_screen_preflight(plan)
    assert preflight.missing_asset_exports == 0
    assert preflight.needs_live_sync is False


def test_resolve_live_sync_auto_when_assets_missing() -> None:
    from figma_flutter_agent.dev.wizard import ScreenPreflight

    preflight = ScreenPreflight(
        feature="music_v2",
        dump_exists=True,
        dump_path=Path("/p/dump.json"),
        wired_feature="music_v2",
        wired_matches=True,
        exportable_icons=3,
        local_icons=0,
        missing_asset_exports=3,
    )
    assert resolve_live_sync(preflight, has_figma_token=True, prefer_live=None) is True
    assert resolve_live_sync(preflight, has_figma_token=False, prefer_live=None) is False
    assert resolve_live_sync(preflight, has_figma_token=True, prefer_live=False) is False


def test_device_id_from_choice() -> None:
    assert device_id_from_choice("Chrome (web) [chrome]") == "chrome"
    assert device_id_from_choice("default — let Flutter choose") is None


def test_default_flutter_device_option_prefers_chrome_web() -> None:
    devices = [
        ("windows", "Windows (desktop)"),
        ("chrome", "Chrome (web-javascript)"),
        ("edge", "Edge (web-javascript)"),
    ]
    assert default_flutter_device_option(devices) == "Chrome (web-javascript) [chrome]"


def test_default_flutter_device_option_falls_back_to_first_device() -> None:
    devices = [
        ("windows", "Windows (desktop)"),
        ("emulator-5554", "sdk gphone64 x86 64 (android-x64)"),
    ]
    assert default_flutter_device_option(devices) == "Windows (desktop) [windows]"


def test_collect_doctor_report(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    (project / "screens.yaml").write_text(
        "file_key: k\nproject_dir: .\nscreens: []\n", encoding="utf-8"
    )
    settings = Settings()
    with patch.dict("os.environ", {"FIGMA_ACCESS_TOKEN": "token"}, clear=False):
        settings = Settings()
        report = collect_doctor_report(project_dir=project, settings=settings)
    names = {item.name for item in report.checks}
    assert "FIGMA_ACCESS_TOKEN" in names
    assert "Flutter project" in names
    assert report.checks[0].ok is True


def test_format_screen_preflight_reflects_full_run_mode() -> None:
    from figma_flutter_agent.dev.wizard import ScreenPreflight

    preflight = ScreenPreflight(
        feature="sign_in",
        dump_exists=True,
        dump_path=Path("/tmp/dump.json"),
        wired_feature="sign_in",
        wired_matches=True,
        exportable_icons=10,
        local_icons=9,
        missing_asset_exports=1,
    )
    full_live = format_screen_preflight(preflight, prefer_live=True)
    assert "will sync from Figma on run" in full_live
    assert "live sync recommended" not in full_live

    offline = format_screen_preflight(preflight, prefer_offline=True)
    assert "offline run, no live asset sync" in offline

    list_view = format_screen_preflight(preflight)
    assert "live sync recommended" in list_view
