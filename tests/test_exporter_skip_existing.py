"""Tests for skip-existing asset export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.figma.connector import ImageUrlFetchResult


@pytest.mark.asyncio
async def test_export_assets_skips_existing_svg_without_images_api(tmp_path: Path) -> None:
    root = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [
            {"id": "1:2", "name": "Logo", "type": "VECTOR", "visible": True},
            {"id": "1:3", "name": "Star", "type": "VECTOR", "visible": True},
        ],
    }
    icons_dir = tmp_path / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    existing = icons_dir / "logo_1_2.svg"
    existing.write_text("<svg></svg>", encoding="utf-8")

    connector = MagicMock()
    connector.fetch_image_urls = AsyncMock(
        return_value=ImageUrlFetchResult(
            urls={"1:3": "https://cdn/star.svg"},
            failed_node_ids=(),
            rate_limited=False,
        )
    )
    connector.download_bytes = AsyncMock(return_value=b"<svg></svg>")

    exporter = AssetExporter(connector)
    outcome = await exporter.export_assets(
        "abc",
        root,
        tmp_path,
        png_scales=[1],
        skip_existing_assets=True,
    )

    connector.fetch_image_urls.assert_awaited_once()
    assert connector.fetch_image_urls.await_args.args[1] == ["1:3"]
    assert {entry.node_id for entry in outcome.manifest.entries} == {"1:2", "1:3"}
