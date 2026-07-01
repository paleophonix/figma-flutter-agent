"""Tests for skip-existing asset export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.figma.images import ImageUrlFetchResult


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


@pytest.mark.asyncio
async def test_export_assets_png_fallback_when_svg_url_missing(tmp_path: Path) -> None:
    root = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [
            {"id": "1:2", "name": "Ok", "type": "VECTOR", "visible": True},
            {"id": "1:3", "name": "Fail", "type": "VECTOR", "visible": True},
        ],
    }

    async def fetch_urls(
        file_key: str,
        node_ids: list[str],
        *,
        fmt: str = "png",
        **kwargs: object,
    ) -> ImageUrlFetchResult:
        if fmt == "svg":
            return ImageUrlFetchResult(
                urls={"1:2": "https://cdn/ok.svg"},
                failed_node_ids=("1:3",),
                rate_limited=False,
            )
        return ImageUrlFetchResult(
            urls={node_id: f"https://cdn/{node_id}.png" for node_id in node_ids},
            failed_node_ids=(),
            rate_limited=False,
        )

    connector = MagicMock()
    connector.fetch_image_urls = AsyncMock(side_effect=fetch_urls)
    connector.download_bytes = AsyncMock(return_value=b"png-bytes")

    exporter = AssetExporter(connector)
    outcome = await exporter.export_assets(
        "abc",
        root,
        tmp_path,
        png_scales=[1],
        blur_png_fallback=True,
    )

    assert {entry.node_id for entry in outcome.manifest.entries} == {"1:2", "1:3"}
    assert outcome.failed_node_ids == frozenset()
    assert (tmp_path / "assets" / "images" / "fail_1_3.png").is_file()


@pytest.mark.asyncio
async def test_export_assets_raster_fallback_node_ids_skip_svg(tmp_path: Path) -> None:
    root = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [
            {"id": "1:2", "name": "Svg", "type": "VECTOR", "visible": True},
            {"id": "1:3", "name": "Raster", "type": "VECTOR", "visible": True},
        ],
    }

    async def fetch_urls(
        file_key: str,
        node_ids: list[str],
        *,
        fmt: str = "png",
        **kwargs: object,
    ) -> ImageUrlFetchResult:
        if fmt == "svg":
            return ImageUrlFetchResult(
                urls={node_id: f"https://cdn/{node_id}.svg" for node_id in node_ids},
                failed_node_ids=(),
                rate_limited=False,
            )
        return ImageUrlFetchResult(
            urls={node_id: f"https://cdn/{node_id}.png" for node_id in node_ids},
            failed_node_ids=(),
            rate_limited=False,
        )

    connector = MagicMock()
    connector.fetch_image_urls = AsyncMock(side_effect=fetch_urls)
    connector.download_bytes = AsyncMock(return_value=b"bytes")

    exporter = AssetExporter(connector)
    outcome = await exporter.export_assets(
        "abc",
        root,
        tmp_path,
        png_scales=[1],
        blur_png_fallback=True,
        restrict_node_ids=frozenset({"1:2", "1:3"}),
        raster_fallback_node_ids=frozenset({"1:3"}),
    )

    first_svg_nodes = connector.fetch_image_urls.await_args_list[0].args[1]
    assert first_svg_nodes == ["1:2"]
    assert {entry.node_id for entry in outcome.manifest.entries} == {"1:2", "1:3"}
    assert (tmp_path / "assets" / "images" / "raster_1_3.png").is_file()
