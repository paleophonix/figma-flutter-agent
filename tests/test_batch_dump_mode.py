"""Tests for batch dump mode planning."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.batch.asset_export import FileAssetExportResult
from figma_flutter_agent.batch.dump_mode import (
    BatchDumpMode,
    DumpWritePolicy,
    assets_attempted,
    frame_fetch_menu_options,
    frame_fetch_mode_from_menu,
    plan_for_mode,
    resolve_batch_dump_mode,
    resolve_skip_existing_screens,
    skip_existing_assets,
)
from figma_flutter_agent.batch.file_dump import dump_full_figma_file
from figma_flutter_agent.figma.models import FigmaFileResponse
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
                        "children": [],
                    },
                ],
            }
        ],
    }


def test_frame_fetch_menu_maps_to_batch_dump_modes() -> None:
    options = frame_fetch_menu_options()
    assert len(options) == 3
    assert frame_fetch_mode_from_menu(options[0]) is BatchDumpMode.ALL
    assert frame_fetch_mode_from_menu(options[1]) is BatchDumpMode.JSON
    assert frame_fetch_mode_from_menu(options[2]) is BatchDumpMode.MEDIA


def test_resolve_batch_dump_mode_legacy_json_only() -> None:
    assert resolve_batch_dump_mode(mode=None, with_assets=False) is BatchDumpMode.JSON
    assert resolve_batch_dump_mode(mode=None, with_assets=True) is BatchDumpMode.ALL
    assert (
        resolve_batch_dump_mode(mode=BatchDumpMode.VECTOR, with_assets=True) is BatchDumpMode.VECTOR
    )


def test_plan_for_media_skips_file_api() -> None:
    plan = plan_for_mode(BatchDumpMode.MEDIA)
    assert plan.fetch_json is False
    assert plan.write_json is False
    assert assets_attempted(plan) is True
    assert plan.export_svg is True
    assert plan.export_raster is True


def test_plan_for_vector_exports_svg_only() -> None:
    plan = plan_for_mode(BatchDumpMode.VECTOR)
    assert plan.export_svg is True
    assert plan.export_raster is False
    assert plan.export_blur_png is False


def test_resolve_skip_existing_screens() -> None:
    assert (
        resolve_skip_existing_screens(
            write_policy=DumpWritePolicy.SKIP_EXISTING,
            skip_existing_screens=None,
        )
        is True
    )
    assert (
        resolve_skip_existing_screens(
            write_policy=DumpWritePolicy.REWRITE,
            skip_existing_screens=True,
        )
        is True
    )
    assert skip_existing_assets(DumpWritePolicy.SKIP_EXISTING) is True


@pytest.mark.asyncio
async def test_dump_vector_mode_uses_cached_json_without_fetch_file(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    debug_dir = project_dir / ".debug"
    debug_dir.mkdir(parents=True)
    (debug_dir / "full_file_abc123.json").write_text(
        json.dumps({"name": "Cached", "document": _sample_document()}),
        encoding="utf-8",
    )
    (project_dir / "pubspec.yaml").write_text(
        "name: demo_app\nflutter:\n  uses-material-design: true\n",
        encoding="utf-8",
    )

    connector = MagicMock()
    connector.fetch_file = AsyncMock()

    empty_manifest = AssetManifest()
    with patch(
        "figma_flutter_agent.batch.asset_export.export_assets_for_document",
        new=AsyncMock(
            return_value=FileAssetExportResult(
                manifest=empty_manifest,
                icon_count=3,
                raster_count=0,
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
            mode=BatchDumpMode.VECTOR,
            write_manifest=False,
        )

    connector.fetch_file.assert_not_called()
    export_mock.assert_awaited_once()
    assert result.mode is BatchDumpMode.VECTOR
    assert result.icon_count == 3
    assert result.raster_count == 0
    assert result.manifest_path is None


@pytest.mark.asyncio
async def test_dump_json_mode_skips_asset_export(tmp_path: Path) -> None:
    connector = MagicMock()
    connector.fetch_file = AsyncMock(
        return_value=FigmaFileResponse.model_validate(
            {
                "name": "Cached",
                "document": _sample_document(),
                "components": {},
                "componentSets": {},
                "styles": {},
            }
        )
    )
    project_dir = tmp_path / "demo"
    project_dir.mkdir()

    with patch(
        "figma_flutter_agent.batch.asset_export.export_assets_for_document",
        new=AsyncMock(),
    ) as export_mock:
        result = await dump_full_figma_file(
            connector,
            file_key="abc123",
            project_dir=project_dir,
            mode=BatchDumpMode.JSON,
        )

    export_mock.assert_not_called()
    assert result.mode is BatchDumpMode.JSON
    connector.fetch_file.assert_awaited_once()
