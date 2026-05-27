"""Optional live Figma API smoke tests (skipped without credentials)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.stages.fetch import fetch_figma_frame

pytestmark = pytest.mark.live_figma


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set")
    return value


@pytest.mark.asyncio
async def test_live_figma_connector_fetch_nodes() -> None:
    """Smoke-test Figma REST connectivity with a configured frame."""
    token = _require_env("FIGMA_ACCESS_TOKEN")
    file_key = _require_env("FIGMA_SMOKE_FILE_KEY")
    node_id = _require_env("FIGMA_SMOKE_NODE_ID")

    async with FigmaConnector(token) as connector:
        response = await connector.fetch_nodes(file_key, [node_id])

    assert node_id in response.nodes
    document = response.nodes[node_id].document
    assert document is not None
    assert document.get("type") == "FRAME"


@pytest.mark.asyncio
async def test_live_figma_fetch_stage(tmp_path: Path) -> None:
    """Smoke-test fetch stage against a live Figma file."""
    token = _require_env("FIGMA_ACCESS_TOKEN")
    file_key = _require_env("FIGMA_SMOKE_FILE_KEY")
    node_id = _require_env("FIGMA_SMOKE_NODE_ID")
    settings = Settings()

    async with FigmaConnector(token, settings.figma_api_base_url) as connector:
        result = await fetch_figma_frame(
            connector,
            file_key=file_key,
            node_id=node_id,
            project_dir=tmp_path,
            verbose=False,
        )

    assert result.root.get("id") == node_id
    assert result.file_key == file_key
