"""Tests for cached-dump asset export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.batch.asset_export import (
    FileAssetExportResult,
    asset_export_gap_hint,
    count_exportable_assets,
    export_screen_assets_from_dump,
    resolve_screen_dump_path,
)
from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry
from figma_flutter_agent.config import AssetsConfig
from figma_flutter_agent.debug.paths import raw_dump_path
from figma_flutter_agent.schemas import AssetManifest


def test_resolve_screen_dump_path_uses_default_when_dump_unset(tmp_path: Path) -> None:
    screen = ScreenEntry(feature="splash", node_id="1:2")
    path = resolve_screen_dump_path(screen, tmp_path)
    assert path == raw_dump_path(tmp_path, "splash")


def test_count_exportable_assets_counts_icons() -> None:
    from figma_flutter_agent.assets.collect import collect_exportable_nodes

    document = {
        "id": "0:1",
        "name": "Frame",
        "type": "FRAME",
        "children": [
            {"id": "1:1", "name": "Star", "type": "STAR", "visible": True},
        ],
    }
    assets = AssetsConfig()
    with patch(
        "figma_flutter_agent.batch.asset_export.collect_exportable_nodes",
        wraps=collect_exportable_nodes,
    ):
        icons, raster = count_exportable_assets(document, assets)
    assert icons == 1
    assert raster == 0


def test_asset_export_gap_hint_rate_limited() -> None:
    document = {"id": "1:1", "name": "Frame", "type": "FRAME", "children": []}
    assets = AssetsConfig()
    result = FileAssetExportResult(
        manifest=AssetManifest(entries=()),
        icon_count=0,
        raster_count=0,
        exported_node_ids=frozenset(),
        failed_node_ids=frozenset({"2:2"}),
        rate_limited=True,
    )
    with patch(
        "figma_flutter_agent.batch.asset_export.count_exportable_assets",
        return_value=(2, 0),
    ):
        hint = asset_export_gap_hint(document, assets, result)
    assert hint is not None
    assert "rate limit" in hint.lower()


@pytest.mark.asyncio
async def test_export_screen_assets_from_dump_reads_cached_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    dump_path = project_dir / ".debug" / "raw" / "splash_layout.json"
    dump_path.parent.mkdir(parents=True)
    document = {"id": "1:1", "name": "Splash", "type": "FRAME", "children": []}
    dump_path.write_text(json.dumps(document), encoding="utf-8")

    manifest = BatchManifest(
        file_key="file123",
        project_dir=project_dir,
        screens=(ScreenEntry(feature="splash", node_id="1:1", dump=dump_path),),
    )
    assets = AssetsConfig()
    expected = FileAssetExportResult(
        manifest=AssetManifest(entries=()),
        icon_count=1,
        raster_count=0,
        exported_node_ids=frozenset({"2:2"}),
        failed_node_ids=frozenset(),
        rate_limited=False,
    )
    connector = AsyncMock()
    with patch(
        "figma_flutter_agent.batch.asset_export.export_assets_for_document",
        new=AsyncMock(return_value=expected),
    ) as export_mock:
        result = await export_screen_assets_from_dump(
            connector,
            manifest=manifest,
            screen=manifest.screens[0],
            assets=assets,
        )

    assert result.icon_count == 1
    export_mock.assert_awaited_once()
    call_kwargs = export_mock.await_args.kwargs
    assert call_kwargs["file_key"] == "file123"
    assert call_kwargs["document"] == document
    assert call_kwargs["project_dir"] == project_dir


@pytest.mark.asyncio
async def test_export_screen_assets_from_dump_missing_dump_raises(tmp_path: Path) -> None:
    manifest = BatchManifest(
        file_key="file123",
        project_dir=tmp_path,
        screens=(ScreenEntry(feature="missing", node_id="1:1"),),
    )
    with pytest.raises(FileNotFoundError, match="No cached dump"):
        await export_screen_assets_from_dump(
            AsyncMock(),
            manifest=manifest,
            screen=manifest.screens[0],
            assets=AssetsConfig(),
        )
