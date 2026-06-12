"""Tests for batch screen purge and copy lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.batch.manifest import (
    load_batch_manifest,
    remove_screens_from_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.batch.models import BatchManifest, ScreenEntry
from figma_flutter_agent.batch.screen_lifecycle import (
    copy_screen_to_project,
    purge_screen_artifacts,
)
from figma_flutter_agent.debug.paths import raw_dump_path


def _write_manifest(path: Path, project_dir: Path, screens: tuple[ScreenEntry, ...]) -> None:
    write_batch_manifest(
        path,
        BatchManifest(file_key="abc123", project_dir=project_dir, screens=screens),
    )


def _write_dump(project_dir: Path, feature: str, node_ids: list[str]) -> Path:
    dump_path = raw_dump_path(project_dir, feature)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    children = [
        {"id": node_id, "name": "icon", "type": "VECTOR", "visible": True, "fills": []}
        for node_id in node_ids
    ]
    payload = {
        "id": "1:1",
        "name": "Frame",
        "type": "FRAME",
        "children": children,
    }
    dump_path.write_text(json.dumps(payload), encoding="utf-8")
    return dump_path


def test_purge_screen_removes_lib_debug_and_exclusive_assets(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    dump_path = _write_dump(project_dir, "sign_in", ["42:100", "42:200"])
    icon_dir = project_dir / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    (icon_dir / "icon_42_100.svg").write_text("<svg/>", encoding="utf-8")
    (icon_dir / "icon_42_200.svg").write_text("<svg/>", encoding="utf-8")

    feature_dir = project_dir / "lib" / "features" / "sign_in"
    feature_dir.mkdir(parents=True)
    screen_path = feature_dir / "sign_in_screen.dart"
    screen_path.write_text(
        "import 'package:demo_app/widgets/only_sign_in_widget.dart';\n",
        encoding="utf-8",
    )
    layout_path = project_dir / "lib" / "generated" / "sign_in_layout.dart"
    layout_path.parent.mkdir(parents=True)
    layout_path.write_text("const x = 1;\n", encoding="utf-8")
    widget_path = project_dir / "lib" / "widgets" / "only_sign_in_widget.dart"
    widget_path.parent.mkdir(parents=True)
    widget_path.write_text("class OnlySignInWidget {}\n", encoding="utf-8")

    manifest_path = project_dir / "screens.yaml"
    _write_manifest(
        manifest_path,
        project_dir,
        (ScreenEntry(feature="sign_in", node_id="1:100", dump=dump_path),),
    )
    manifest = load_batch_manifest(manifest_path)

    summary = purge_screen_artifacts(manifest, "sign_in")
    remove_screens_from_manifest(manifest_path, ["sign_in"])

    assert summary.total_files >= 5
    assert not screen_path.is_file()
    assert not layout_path.is_file()
    assert not widget_path.is_file()
    assert not (icon_dir / "icon_42_100.svg").is_file()
    assert not dump_path.is_file()
    assert load_batch_manifest(manifest_path).screens == ()


def test_purge_retains_assets_shared_with_remaining_screen(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    shared_id = "42:999"
    sign_in_dump = _write_dump(project_dir, "sign_in", [shared_id])
    home_dump = _write_dump(project_dir, "home", [shared_id])
    icon_dir = project_dir / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    shared_icon = icon_dir / "icon_42_999.svg"
    shared_icon.write_text("<svg/>", encoding="utf-8")

    manifest_path = project_dir / "screens.yaml"
    _write_manifest(
        manifest_path,
        project_dir,
        (
            ScreenEntry(feature="sign_in", node_id="1:100", dump=sign_in_dump),
            ScreenEntry(feature="home", node_id="1:200", dump=home_dump),
        ),
    )
    manifest = load_batch_manifest(manifest_path)

    purge_screen_artifacts(manifest, "sign_in")

    assert shared_icon.is_file()


def test_copy_screen_to_project_transfers_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    dump_path = _write_dump(source, "profile", ["42:555"])
    layout_path = source / "lib" / "generated" / "profile_layout.dart"
    layout_path.parent.mkdir(parents=True)
    layout_path.write_text("class ProfileLayout {}\n", encoding="utf-8")

    source_manifest_path = source / "screens.yaml"
    _write_manifest(
        source_manifest_path,
        source,
        (ScreenEntry(feature="profile", node_id="1:300", dump=dump_path),),
    )
    target_manifest_path = target / "screens.yaml"
    _write_manifest(target_manifest_path, target, ())

    manifest = load_batch_manifest(source_manifest_path)
    summary = copy_screen_to_project(manifest, "profile", target)

    assert summary.total_files >= 2
    assert (target / "lib" / "generated" / "profile_layout.dart").is_file()
    assert raw_dump_path(target, "profile").is_file()
    target_manifest = load_batch_manifest(target_manifest_path)
    assert len(target_manifest.screens) == 1
    assert target_manifest.screens[0].feature == "profile"
