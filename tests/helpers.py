"""Typed helpers for Figma connector and pipeline mocks in tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

from figma_flutter_agent.figma.connector import ImageUrlFetchResult
from figma_flutter_agent.pipeline.deps import PipelineDependencies, default_pipeline_dependencies


class _FigmaConnectorContext:
    """Minimal async context manager yielding a mock connector."""

    def __init__(self, connector: MagicMock) -> None:
        self._connector = connector

    async def __aenter__(self) -> MagicMock:
        return self._connector

    async def __aexit__(self, *args: object) -> None:
        return None


def figma_connector_factory(connector: MagicMock) -> Callable[[str, str], _FigmaConnectorContext]:
    """Return a ``PipelineDependencies.figma_connector`` callable for tests."""

    def _factory(_token: str, _base_url: str) -> _FigmaConnectorContext:
        return _FigmaConnectorContext(connector)

    return _factory


def pipeline_test_dependencies(
    *,
    connector: MagicMock | None = None,
    create_llm_client: Any | None = None,
) -> PipelineDependencies:
    """Build injectable pipeline deps with mock Figma/LLM defaults."""
    base = default_pipeline_dependencies()
    mock_connector = wire_connector(connector or MagicMock())
    llm_factory = create_llm_client or MagicMock()
    return PipelineDependencies(
        figma_connector=figma_connector_factory(mock_connector),
        create_llm_client=llm_factory,
        create_llm_repair_client=llm_factory,
        create_llm_refine_client=llm_factory,
        commit_planned_files=base.commit_planned_files,
        dart_writer_factory=base.dart_writer_factory,
    )


async def mock_fetch_nodes(*args: Any, **kwargs: Any) -> MagicMock:
    """Return a minimal Figma nodes API response."""
    entry = MagicMock()
    entry.document = {
        "id": "1:1",
        "name": "Screen",
        "type": "FRAME",
        "visible": True,
        "children": [],
    }
    response = MagicMock()
    response.nodes = {"1:1": entry}
    return response


async def mock_fetch_variables(*args: Any, **kwargs: Any) -> None:
    return None


async def mock_fetch_styles(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {}


async def mock_fetch_components(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {}


async def mock_fetch_image_urls(*args: Any, **kwargs: Any) -> ImageUrlFetchResult:
    return ImageUrlFetchResult(urls={}, failed_node_ids=(), rate_limited=False)


def wire_connector(connector: MagicMock) -> MagicMock:
    """Attach standard async fetch mocks to a connector MagicMock."""
    connector.fetch_nodes = mock_fetch_nodes
    connector.fetch_variables = mock_fetch_variables
    connector.fetch_styles = mock_fetch_styles
    connector.fetch_components = mock_fetch_components
    connector.fetch_image_urls = mock_fetch_image_urls
    return connector


def write_minimal_batch_manifest(project_dir: Path, *, file_key: str = "abc") -> None:
    """Write an empty ``screens.yaml`` so pipeline tests avoid manifest auto-create."""
    (project_dir / "screens.yaml").write_text(
        f"file_key: {file_key}\nproject_dir: .\nscreens: []\n",
        encoding="utf-8",
    )


@asynccontextmanager
async def mock_connector_context(*args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
    """Async context manager matching ``FigmaConnector`` usage in the pipeline."""
    yield wire_connector(MagicMock())
