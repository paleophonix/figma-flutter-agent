import time

import httpx
import pytest
import respx
from httpx import Response

from figma_flutter_agent.errors import FigmaApiError
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.figma.limits import BATCH_SIZE
from figma_flutter_agent.figma.nodes import merge_figma_nodes_batch


@pytest.mark.asyncio
@respx.mock
async def test_fetch_nodes_batches_large_id_lists() -> None:
    node_ids = [f"{index}:1" for index in range(25)]
    route = respx.get(url__regex=r"https://api\.figma\.com/v1/files/abc/nodes.*").mock(
        side_effect=lambda request: Response(
            200,
            json={
                "name": "File",
                "nodes": {
                    node_id: {"document": {"id": node_id, "type": "FRAME"}}
                    for node_id in request.url.params["ids"].split(",")
                },
            },
        )
    )

    async with FigmaConnector("figd_test") as connector:
        response = await connector.fetch_nodes("abc", node_ids)

    assert route.call_count == 2
    assert len(response.nodes) == 25
    assert all(len(call.request.url.params["ids"].split(",")) <= BATCH_SIZE for call in route.calls)


def test_merge_figma_nodes_batch_skips_null_entries() -> None:
    merged: dict[str, object] = {}
    dropped = merge_figma_nodes_batch(
        merged,
        {
            "1:1": {"document": {"id": "1:1"}},
            "1:2": None,
        },
    )
    assert dropped == ["1:2"]
    assert merged == {"1:1": {"document": {"id": "1:1"}}}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_nodes_ignores_null_api_entries() -> None:
    respx.get("https://api.figma.com/v1/files/abc/nodes").mock(
        return_value=Response(
            200,
            json={
                "name": "File",
                "nodes": {
                    "1:1": {
                        "document": {"id": "1:1", "name": "Screen", "type": "FRAME", "children": []}
                    },
                    "1:1192": None,
                },
            },
        )
    )

    async with FigmaConnector("figd_test") as connector:
        response = await connector.fetch_nodes("abc", ["1:1", "1:1192"])

    assert "1:1" in response.nodes
    assert "1:1192" not in response.nodes


@pytest.mark.asyncio
@respx.mock
async def test_fetch_nodes_returns_parsed_response() -> None:
    respx.get("https://api.figma.com/v1/files/abc/nodes").mock(
        return_value=Response(
            200,
            json={
                "name": "File",
                "nodes": {
                    "1:1": {
                        "document": {"id": "1:1", "name": "Screen", "type": "FRAME", "children": []}
                    }
                },
            },
        )
    )

    async with FigmaConnector("figd_test") as connector:
        response = await connector.fetch_nodes("abc", ["1:1"])

    assert "1:1" in response.nodes
    assert response.nodes["1:1"].document is not None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_variables_returns_none_on_403() -> None:
    respx.get("https://api.figma.com/v1/files/abc/variables/local").mock(return_value=Response(403))

    async with FigmaConnector("figd_test") as connector:
        payload = await connector.fetch_variables("abc")

    assert payload is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_variables_returns_none_on_404() -> None:
    respx.get("https://api.figma.com/v1/files/abc/variables/local").mock(
        return_value=Response(404, json={"status": 404, "err": "Not found"}),
    )

    async with FigmaConnector("figd_test") as connector:
        payload = await connector.fetch_variables("abc")

    assert payload is None


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_429() -> None:
    route = respx.get("https://api.figma.com/v1/files/abc/nodes").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "0"}, text="rate limited"),
            Response(
                200,
                json={
                    "name": "File",
                    "nodes": {"1:1": {"document": {"id": "1:1", "type": "FRAME"}}},
                },
            ),
        ]
    )

    async with FigmaConnector("figd_test") as connector:
        response = await connector.fetch_nodes("abc", ["1:1"])

    assert route.call_count == 2
    assert "1:1" in response.nodes


@pytest.mark.asyncio
@respx.mock
async def test_fetch_image_urls_continue_on_rate_limit() -> None:
    node_ids = [f"{index}:1" for index in range(25)]
    route = respx.get(url__regex=r"https://api\.figma\.com/v1/images/abc.*").mock(
        side_effect=[
            Response(200, json={"images": {node_ids[0]: "https://cdn/0.png"}}),
            Response(
                429,
                headers={"Retry-After": "382044", "X-Figma-Plan-Tier": "starter"},
                text="rate limited",
            ),
        ]
    )

    async with FigmaConnector("figd_test") as connector:
        result = await connector.fetch_image_urls(
            "abc",
            node_ids,
            continue_on_rate_limit=True,
        )

    assert route.call_count == 2
    assert result.urls == {node_ids[0]: "https://cdn/0.png"}
    assert set(result.failed_node_ids) == set(node_ids[20:])
    assert result.rate_limited is True


@pytest.mark.asyncio
async def test_connector_requires_context_manager() -> None:
    connector = FigmaConnector("figd_test")
    with pytest.raises(FigmaApiError, match="async context manager"):
        await connector.fetch_nodes("abc", ["1:1"])


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_connect_timeout() -> None:
    route = respx.get("https://api.figma.com/v1/files/abc/nodes").mock(
        side_effect=[
            httpx.ConnectTimeout(""),
            Response(
                200,
                json={
                    "name": "File",
                    "nodes": {"1:1": {"document": {"id": "1:1", "type": "FRAME"}}},
                },
            ),
        ]
    )

    async with FigmaConnector("figd_test") as connector:
        response = await connector.fetch_nodes("abc", ["1:1"])

    assert route.call_count == 2
    assert "1:1" in response.nodes


@pytest.mark.asyncio
@respx.mock
async def test_transport_failure_message_after_exhausted_retries() -> None:
    route = respx.get("https://api.figma.com/v1/files/abc/nodes").mock(
        side_effect=httpx.ConnectTimeout("")
    )

    async with FigmaConnector("figd_test") as connector:
        with pytest.raises(FigmaApiError, match="ConnectTimeout") as exc_info:
            await connector.fetch_nodes("abc", ["1:1"])

    assert route.call_count == 3
    assert "offline mode" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_request_fails_fast_when_retry_after_is_huge() -> None:
    respx.get("https://api.figma.com/v1/files/abc/styles").mock(
        return_value=Response(
            429,
            headers={
                "Retry-After": "382044",
                "X-Figma-Plan-Tier": "starter",
                "X-Figma-Rate-Limit-Type": "low",
            },
            text="rate limited",
        )
    )

    async with FigmaConnector("figd_test") as connector:
        with pytest.raises(FigmaApiError, match="382044") as exc_info:
            await connector.fetch_styles("abc")

    assert exc_info.value.status_code == 429
    assert "Automatic retry is capped" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_parse_retry_after_treats_unix_timestamp_as_absolute() -> None:
    future_ts = str(int(time.time()) + 60)
    delay = FigmaConnector._parse_retry_after_seconds(future_ts)
    assert delay is not None
    assert 55 <= delay <= 65


@pytest.mark.asyncio
@respx.mock
async def test_fetch_styles_returns_published_map() -> None:
    respx.get("https://api.figma.com/v1/files/abc/styles").mock(
        return_value=Response(
            200,
            json={"meta": {"styles": {"style-1": {"name": "Brand/Primary", "styleType": "FILL"}}}},
        )
    )

    async with FigmaConnector("figd_test") as connector:
        styles = await connector.fetch_styles("abc")

    assert styles["style-1"]["name"] == "Brand/Primary"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_components_returns_published_map() -> None:
    respx.get("https://api.figma.com/v1/files/abc/components").mock(
        return_value=Response(
            200,
            json={
                "meta": {"components": {"comp-1": {"name": "Button", "componentSetId": "set-1"}}}
            },
        )
    )

    async with FigmaConnector("figd_test") as connector:
        components = await connector.fetch_components("abc")

    assert components["comp-1"]["name"] == "Button"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_component_sets_returns_published_map() -> None:
    respx.get("https://api.figma.com/v1/files/abc/component_sets").mock(
        return_value=Response(
            200,
            json={"meta": {"component_sets": {"set-1": {"name": "Button"}}}},
        )
    )

    async with FigmaConnector("figd_test") as connector:
        component_sets = await connector.fetch_component_sets("abc")

    assert component_sets["set-1"]["name"] == "Button"
