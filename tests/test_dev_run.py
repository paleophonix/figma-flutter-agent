"""Tests for dev run workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    find_screen_entry,
    format_screen_list,
    load_batch_manifest,
)
from figma_flutter_agent.dev.project import ensure_project_config
from figma_flutter_agent.dev.run import (
    _flutter_run_stopped,
    detect_wired_screen_feature,
    launch_flutter_app,
    plan_run_screen,
)
from figma_flutter_agent.errors import FlutterProjectError


def test_find_screen_entry_exact_and_alias() -> None:
    manifest = BatchManifest(
        file_key="abc",
        project_dir=Path("/proj"),
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:3570"),
            ScreenEntry(feature="home", node_id="1:2"),
        ),
    )
    assert find_screen_entry(manifest, "sign_in").node_id == "1:3570"
    assert find_screen_entry(manifest, "sign-in").feature == "sign_in"
    assert find_screen_entry(manifest, "Sign In").feature == "sign_in"


def test_find_screen_entry_unknown_raises() -> None:
    manifest = BatchManifest(
        file_key="abc",
        project_dir=Path("/proj"),
        screens=(ScreenEntry(feature="home", node_id="1:2"),),
    )
    with pytest.raises(ValueError, match="Unknown screen"):
        find_screen_entry(manifest, "missing")


def test_plan_run_screen(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
    dump_dir = project / ".figma_debug" / "raw"
    dump_dir.mkdir(parents=True)
    dump_path = dump_dir / "sign_in_layout.json"
    dump_path.write_text(
        '{"id": "1:3570", "name": "SignIn", "type": "FRAME", "children": []}', encoding="utf-8"
    )
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: sign_in",
                "    node_id: 1:3570",
                "    dump: .figma_debug/raw/sign_in_layout.json",
            ]
        ),
        encoding="utf-8",
    )
    example = Path(__file__).resolve().parents[1] / ".ai-figma-flutter.yml.example"
    if example.is_file():
        (project / ".ai-figma-flutter.yml").write_text(
            example.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        ensure_project_config(project)

    plan = plan_run_screen(project_dir=project, screen_name="sign_in")
    assert plan.screen.feature == "sign_in"
    assert plan.dump_path == dump_path
    assert "node-id=1-3570" in plan.figma_url


def test_load_batch_manifest_from_repo_example() -> None:
    manifest_path = Path(__file__).resolve().parents[1] / "screens.example.yaml"
    if not manifest_path.is_file():
        pytest.skip("screens.example.yaml missing")
    manifest = load_batch_manifest(manifest_path)
    assert manifest.file_key
    assert manifest.screens


def test_detect_wired_screen_feature_from_main_dart(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    lib = project / "lib"
    lib.mkdir(parents=True)
    (lib / "main.dart").write_text(
        "import 'package:demo_app/features/sign_in/sign_in_screen.dart';\n"
        "home: const SignInScreen(),\n",
        encoding="utf-8",
    )
    assert detect_wired_screen_feature(project) == "sign_in"


def test_format_screen_list_marks_active() -> None:
    manifest = BatchManifest(
        file_key="abc",
        project_dir=Path("/proj"),
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:1"),
            ScreenEntry(feature="home", node_id="1:2"),
        ),
    )
    rendered = format_screen_list(manifest, active="sign_in")
    assert "Active screen (main.dart): sign_in" in rendered
    assert "1. * sign_in" in rendered
    assert "2.   home" in rendered


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [
        (0, False),
        (1, False),
        (130, True),
        (255, True),
        (3221225786, True),
        (-1073741510, True),
        (-1, True),
    ],
)
def test_flutter_run_stopped(returncode: int, expected: bool) -> None:
    assert _flutter_run_stopped(returncode) is expected


def test_launch_flutter_app_returns_false_when_user_stops(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()

    with (
        patch(
            "figma_flutter_agent.dev.run.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.run.subprocess.run",
            side_effect=[
                None,
                subprocess.CalledProcessError(255, ["flutter", "run"]),
            ],
        ),
    ):
        launched = launch_flutter_app(project)

    assert launched is False


def test_launch_flutter_app_raises_on_build_failure(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()

    with (
        patch(
            "figma_flutter_agent.dev.run.require_flutter_executable",
            return_value="flutter",
        ),
        patch(
            "figma_flutter_agent.dev.run.subprocess.run",
            side_effect=[
                None,
                subprocess.CalledProcessError(1, ["flutter", "run"]),
            ],
        ),
        pytest.raises(FlutterProjectError, match="flutter run failed"),
    ):
        launch_flutter_app(project)


def test_launch_flutter_app_uses_no_pub_for_run(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    calls: list[list[str]] = []

    def _record(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    with (
        patch(
            "figma_flutter_agent.dev.run.require_flutter_executable",
            return_value="flutter",
        ),
        patch("figma_flutter_agent.dev.run.subprocess.run", side_effect=_record),
    ):
        launch_flutter_app(project, device_id="chrome")

    assert calls[0] == ["flutter", "pub", "get"]
    assert calls[1] == ["flutter", "run", "--no-pub", "-d", "chrome"]
