"""Golden capture asset sync and workspace selection."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing
from figma_flutter_agent.validation.golden_capture import (
    _copy_skeleton_project,
    _read_figma_key_rects,
    _sync_project_assets,
    collect_planned_asset_paths,
)


def test_collect_planned_asset_paths_from_dart_strings() -> None:
    planned = {
        "lib/features/sign_in/sign_in_screen.dart": (
            "SvgPicture.asset('assets/icons/vector_1_3576.svg');\n"
            'Image.asset("assets/icons/other.svg");'
        ),
    }
    paths = collect_planned_asset_paths(planned)
    assert paths == {
        "assets/icons/vector_1_3576.svg",
        "assets/icons/other.svg",
    }


def test_collect_planned_asset_paths_includes_layout_tree_vectors(tmp_path: Path) -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="icon",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/from_tree.svg",
            ),
        ],
    )
    paths = collect_planned_asset_paths({}, layout_tree=root)
    assert "assets/icons/from_tree.svg" in paths


def test_collect_planned_asset_paths_includes_layout_tree_raster() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:3",
                name="hero",
                type=NodeType.IMAGE,
                image_asset_key="assets/illustrations/hero_1_3.png",
            ),
        ],
    )
    paths = collect_planned_asset_paths({}, layout_tree=root)
    assert "assets/illustrations/hero_1_3.png" in paths


def test_golden_capture_pubspec_lists_synced_raster_dirs(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    source = tmp_path / "source"
    _copy_skeleton_project(capture)
    raster = source / "assets" / "images" / "logo_1_1.png"
    raster.parent.mkdir(parents=True)
    raster.write_bytes(b"\x89PNG\r\n\x1a\n")
    source_pubspec = source / "pubspec.yaml"
    source_pubspec.write_text(
        "name: demo_app\n"
        "environment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n"
        "flutter:\n  uses-material-design: true\n"
        "  assets:\n    - assets/icons/\n    - assets/images/\n",
        encoding="utf-8",
    )
    planned = {
        "lib/features/demo/demo_screen.dart": ("Image.asset('assets/images/logo_1_1.png');"),
    }
    _sync_project_assets(capture, source, planned=planned)
    assert (capture / "assets" / "images" / "logo_1_1.png").is_file()
    yaml = YAML()
    data = yaml.load((capture / "pubspec.yaml").read_text(encoding="utf-8"))
    asset_dirs = {str(item) for item in data["flutter"]["assets"]}
    assert "assets/images/" in asset_dirs


def test_read_figma_key_rects_ignores_empty_file(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    keys = capture / "test" / "goldens" / "demo_figma_keys.json"
    keys.parent.mkdir(parents=True)
    keys.write_text("", encoding="utf-8")
    assert _read_figma_key_rects(capture, "demo") is None


def test_sync_project_assets_merges_package_name_from_source(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    source = tmp_path / "source"
    source.mkdir()
    _copy_skeleton_project(capture)
    (source / "pubspec.yaml").write_text(
        "name: inbox\n"
        "environment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n"
        "flutter:\n  uses-material-design: true\n",
        encoding="utf-8",
    )
    _sync_project_assets(
        capture,
        source,
        planned={"lib/features/login/login_screen.dart": "const SizedBox();"},
    )
    yaml = YAML()
    data = yaml.load((capture / "pubspec.yaml").read_text(encoding="utf-8"))
    assert data["name"] == "inbox"


def test_merge_pubspec_creates_asset_dirs_without_synced_files(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    source = tmp_path / "source"
    source.mkdir()
    _copy_skeleton_project(capture)
    source_pubspec = source / "pubspec.yaml"
    source_pubspec.write_text(
        "name: demo_app\n"
        "environment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n"
        "flutter:\n  uses-material-design: true\n"
        "  assets:\n    - assets/images/\n",
        encoding="utf-8",
    )
    _sync_project_assets(
        capture,
        source,
        planned={"lib/features/demo/demo_screen.dart": "const SizedBox();"},
    )
    assert (capture / "assets" / "images").is_dir()
