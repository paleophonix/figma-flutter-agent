"""Tests for full-file batch dump."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.batch.asset_export import FileAssetExportResult
from figma_flutter_agent.batch.dump_mode import BatchDumpMode
from figma_flutter_agent.batch.file_dump import dump_full_figma_file
from figma_flutter_agent.batch.frames import discover_page_level_frames
from figma_flutter_agent.batch.manifest import (
    BatchManifest,
    ScreenEntry,
    load_batch_manifest,
    write_batch_manifest,
)
from figma_flutter_agent.batch.screen_report import build_screen_download_reports
from figma_flutter_agent.debug.paths import raw_dump_path
from figma_flutter_agent.figma.models import FigmaFileResponse
from figma_flutter_agent.figma.url import parse_figma_file_key
from figma_flutter_agent.schemas import AssetManifest


def _sample_document() -> dict:
    return {
        "id": "0:0",
        "name": "Document",
        "type": "DOCUMENT",
        "children": [
            {
                "id": "0:1",
                "name": "Screens",
                "type": "CANVAS",
                "children": [
                    {
                        "id": "1:100",
                        "name": "Sign In",
                        "type": "FRAME",
                        "visible": True,
                        "children": [{"id": "1:101", "name": "Title", "type": "TEXT"}],
                    },
                    {
                        "id": "1:200",
                        "name": "Home",
                        "type": "FRAME",
                        "visible": True,
                        "children": [],
                    },
                    {
                        "id": "1:300",
                        "name": "Hidden",
                        "type": "FRAME",
                        "visible": False,
                        "children": [],
                    },
                ],
            }
        ],
    }


def test_discover_page_level_frames() -> None:
    frames = discover_page_level_frames(_sample_document())
    assert [frame["id"] for frame in frames] == ["1:100", "1:200"]


def test_parse_figma_file_key_without_node_id() -> None:
    key = parse_figma_file_key("https://www.figma.com/design/abc123/My-File")
    assert key == "abc123"


@pytest.mark.asyncio
async def test_dump_full_figma_file_writes_manifest_and_screens(
    tmp_path: Path,
    debug_agent_root: Path,  # noqa: ARG001 — routes agent .debug under tmp_path
) -> None:
    connector = MagicMock()
    connector.fetch_file = AsyncMock(
        return_value=FigmaFileResponse.model_validate(
            {
                "name": "Meditation",
                "document": _sample_document(),
                "components": {},
                "componentSets": {},
                "styles": {},
            }
        )
    )
    project_dir = tmp_path / "demo"
    project_dir.mkdir()

    result = await dump_full_figma_file(
        connector,
        file_key="abc123",
        project_dir=project_dir,
        mode=BatchDumpMode.JSON,
    )

    assert len(result.screens) == 2
    assert result.full_file_path.is_file()
    assert result.manifest_path is not None
    assert result.manifest_path.is_file()

    manifest = load_batch_manifest(result.manifest_path)
    assert manifest.file_key == "abc123"
    assert len(manifest.screens) == 2
    assert manifest.screens[0].feature == "sign_in"
    assert manifest.screens[1].feature == "home"

    dump_one = raw_dump_path(project_dir, "sign_in")
    assert dump_one.is_file()
    payload = json.loads(dump_one.read_text(encoding="utf-8"))
    assert payload["name"] == "Sign In"
    connector.fetch_file.assert_awaited_once_with("abc123")


@pytest.mark.asyncio
async def test_dump_full_figma_file_merges_manifest(tmp_path: Path) -> None:
    connector = MagicMock()
    connector.fetch_file = AsyncMock(
        return_value=FigmaFileResponse.model_validate(
            {
                "name": "Meditation",
                "document": _sample_document(),
                "components": {},
                "componentSets": {},
                "styles": {},
            }
        )
    )
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    manifest_path = project_dir / "screens.yaml"
    write_batch_manifest(
        manifest_path,
        BatchManifest(
            file_key="abc123",
            project_dir=project_dir,
            screens=(ScreenEntry(feature="profile", node_id="9:999"),),
        ),
    )

    await dump_full_figma_file(
        connector,
        file_key="abc123",
        project_dir=project_dir,
        manifest_path=manifest_path,
        mode=BatchDumpMode.JSON,
        manifest_merge=True,
    )

    manifest = load_batch_manifest(manifest_path)
    assert [screen.feature for screen in manifest.screens] == ["profile", "sign_in", "home"]


@pytest.mark.asyncio
async def test_dump_full_figma_file_exports_assets_by_default(tmp_path: Path) -> None:
    connector = MagicMock()
    connector.fetch_file = AsyncMock(
        return_value=FigmaFileResponse.model_validate(
            {
                "name": "Meditation",
                "document": _sample_document(),
                "components": {},
                "componentSets": {},
                "styles": {},
            }
        )
    )
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text(
        "name: demo_app\nflutter:\n  uses-material-design: true\n",
        encoding="utf-8",
    )

    empty_manifest = AssetManifest()

    with patch(
        "figma_flutter_agent.batch.asset_export.export_assets_for_document",
        new=AsyncMock(
            return_value=FileAssetExportResult(
                manifest=empty_manifest,
                icon_count=12,
                raster_count=4,
                exported_node_ids=frozenset(),
                failed_node_ids=frozenset(),
                rate_limited=False,
            )
        ),
    ) as export_mock:
        result = await dump_full_figma_file(
            connector,
            file_key="abc123",
            project_dir=project_dir,
            mode=BatchDumpMode.ALL,
        )

    assert result.icon_count == 12
    assert result.raster_count == 4
    export_mock.assert_awaited_once()


def test_build_screen_download_reports_marks_partial_assets() -> None:
    frame = {
        "id": "1:100",
        "name": "Sign In",
        "type": "FRAME",
        "visible": True,
        "children": [
            {"id": "1:101", "name": "Logo", "type": "VECTOR", "visible": True},
            {"id": "1:102", "name": "Hero", "type": "VECTOR", "visible": True},
        ],
    }
    dump_path = Path("raw_node_1_100.json")
    reports, orphans = build_screen_download_reports(
        [("sign_in", "1:100", "Sign In", dump_path, False)],
        frames_by_id={"1:100": frame},
        exported_node_ids={"1:101"},
        assets_attempted=True,
    )

    assert len(reports) == 1
    assert reports[0].json_status == "missing"
    assert reports[0].asset_status == "partial"
    assert reports[0].assets_exported == 1
    assert reports[0].assets_expected == 2
    assert orphans == set()
