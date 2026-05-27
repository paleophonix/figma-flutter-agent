"""Tests for offline pipeline generation from cached Figma dumps."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import AssetManifest
from tests.helpers import pipeline_test_dependencies


def test_load_fetch_result_from_dump(tmp_path: Path) -> None:
    root = {"id": "24:105", "name": "Screen", "type": "FRAME", "children": []}
    dump_path = tmp_path / "raw_node_24_105.json"
    dump_path.write_text(json.dumps(root), encoding="utf-8")

    result = load_fetch_result_from_dump(dump_path, file_key="abc", node_id="24:105")

    assert result.file_key == "abc"
    assert result.node_id == "24:105"
    assert result.root == root


def test_local_asset_manifest_from_project(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "icon_1_3570.svg").write_text("<svg/>", encoding="utf-8")
    (icons / "not_a_node.svg").write_text("<svg/>", encoding="utf-8")

    manifest = local_asset_manifest_from_project(tmp_path)

    assert isinstance(manifest, AssetManifest)
    assert len(manifest.entries) == 1
    assert manifest.entries[0].node_id == "1:3570"
    assert manifest.entries[0].asset_path == "assets/icons/icon_1_3570.svg"


@pytest.mark.asyncio
async def test_run_pipeline_from_dump_skips_figma_api(tmp_path: Path) -> None:
    from figma_flutter_agent import pipeline as pipeline_module

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )
    dump_path = project_dir / ".figma_debug" / "raw" / "sign_in_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text(
        json.dumps(
            {
                "id": "1:3570",
                "name": "SignIn",
                "type": "FRAME",
                "visible": True,
                "children": [],
            }
        ),
        encoding="utf-8",
    )

    settings = Settings()
    deps = pipeline_test_dependencies()
    fetch_mock = AsyncMock()

    with (
        patch.object(
            pipeline_module,
            "parse_figma_url",
            return_value=MagicMock(file_key="abc", node_id="1:3570"),
        ),
        patch.object(pipeline_module, "fetch_figma_frame", fetch_mock),
    ):
        result = await pipeline_module.run_pipeline(
            settings,
            figma_url="https://www.figma.com/design/abc/x?node-id=1-3570",
            project_dir=project_dir,
            feature_name="sign_in",
            dry_run=True,
            sync_enabled=False,
            from_dump=dump_path,
            deps=deps,
        )

    fetch_mock.assert_not_called()
    assert result.clean_tree.name == "SignIn"
    assert any("sign_in" in path for path in result.planned_files)
