"""Asset export criterion for spec-23."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.exporter import AssetExporter
from figma_flutter_agent.assets.models import AssetExportOutcome
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.figma.images import ImageUrlFetchResult
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult


def _criterion_asset_export(root: dict[str, Any], *, strict: bool) -> Spec23CriterionResult:
    exportables = collect_exportable_nodes(root)
    if not strict:
        return Spec23CriterionResult(
            name="asset_export",
            passed=isinstance(exportables, list),
            detail=f"exportable_nodes={len(exportables)}",
        )

    passed = True
    detail = f"exportable_nodes={len(exportables)}"

    if exportables:
        mock_connector = MagicMock(spec=FigmaConnector)

        async def mock_fetch_urls(*args: Any, **kwargs: Any) -> ImageUrlFetchResult:
            return ImageUrlFetchResult(
                urls={node_id: f"https://example.com/{node_id}.svg" for node_id, _, _ in exportables},
                failed_node_ids=(),
                rate_limited=False,
            )

        async def mock_download(*args: Any, **kwargs: Any) -> bytes:
            return b"<svg></svg>"

        mock_connector.fetch_image_urls = mock_fetch_urls
        mock_connector.download_bytes = mock_download

        exporter = AssetExporter(mock_connector)
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)

            async def run_export() -> AssetExportOutcome:
                return await exporter.export_assets(
                    "dummy_key",
                    root,
                    project_dir,
                    svg_enabled=True,
                    png_scales=[1],
                )

            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    from concurrent.futures import ThreadPoolExecutor

                    with ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, run_export())
                        outcome = future.result()
                else:
                    outcome = asyncio.run(run_export())

                manifest = outcome.manifest
                written_files = list(project_dir.glob("assets/**/*"))
                if not written_files or not manifest.entries:
                    passed = False
                    detail = f"{detail}; export failed (no files written)"
                else:
                    detail = f"{detail}; verified export ({len(written_files)} files)"
            except Exception as exc:
                passed = False
                detail = f"{detail}; export error: {exc}"

    return Spec23CriterionResult(name="asset_export", passed=passed, detail=detail)
