import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.figma.images import ImageUrlFetchResult
from figma_flutter_agent.validation.reference import (
    collect_layout_metric_warnings,
    export_figma_reference,
)


def test_collect_layout_metric_warnings_flags_wide_frames() -> None:
    warnings = collect_layout_metric_warnings(
        {"absoluteBoundingBox": {"width": 720, "height": 1280}},
        max_web_width=480,
    )

    assert any("maxWebWidth" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_export_figma_reference_writes_png_and_metadata(tmp_path: Path) -> None:
    connector = MagicMock()
    connector.fetch_image_urls = AsyncMock(
        return_value=ImageUrlFetchResult(
            urls={"1:1": "https://figma.test/image.png"},
            failed_node_ids=(),
            rate_limited=False,
        )
    )
    connector.download_bytes = AsyncMock(return_value=b"fake-png-bytes")

    export = await export_figma_reference(
        connector,
        file_key="abc",
        node_id="1:1",
        project_dir=tmp_path,
        feature_name="onboarding",
        figma_root={"absoluteBoundingBox": {"width": 360, "height": 640}},
        scale=2.0,
    )

    assert export is not None
    assert export.image_path.is_file()
    metadata = json.loads(export.metadata_path.read_text(encoding="utf-8"))
    assert metadata["featureName"] == "onboarding"
    assert metadata["width"] == 360
    assert export.image_hash
