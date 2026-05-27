from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.generator.destinations import generate_destination_screens
from figma_flutter_agent.parser.navigation import (
    RouteDefinition,
    build_feature_routes,
    route_class_for,
)
from figma_flutter_agent.schemas import DesignTokens, FlutterGenerationResponse


@pytest.mark.asyncio
async def test_generate_destination_screens_skips_current_feature() -> None:
    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(
            screen_code="class DetailsScreen extends StatelessWidget {}"
        )
    )
    routes = build_feature_routes("onboarding", node_id="1:1")
    routes.append(
        RouteDefinition(
            name="details",
            path="/details",
            screen_class="DetailsScreen",
            route_class=route_class_for("DetailsScreen"),
            import_path="../../features/details/details_screen.dart",
            node_id="2:1",
        )
    )

    responses, warnings = await generate_destination_screens(
        llm,
        routes=routes,
        current_feature="onboarding",
        frame_index={
            "2:1": {"id": "2:1", "name": "Details", "type": "FRAME", "children": []},
        },
        tokens=DesignTokens(),
        asset_manifest=[],
        navigation_hints=[],
        published_styles=None,
        components=None,
        routing_enabled=True,
    )

    assert "details" in responses
    llm.generate_async.assert_awaited_once()
    assert warnings == []


@pytest.mark.asyncio
async def test_generate_destination_screens_uses_prebuilt_trees() -> None:
    llm = MagicMock()
    llm.generate_async = AsyncMock(
        return_value=FlutterGenerationResponse(
            screen_code="class DetailsScreen extends StatelessWidget {}"
        )
    )
    routes = build_feature_routes("onboarding", node_id="1:1")
    routes.append(
        RouteDefinition(
            name="details",
            path="/details",
            screen_class="DetailsScreen",
            route_class=route_class_for("DetailsScreen"),
            import_path="../../features/details/details_screen.dart",
            node_id="2:1",
        )
    )
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

    prebuilt_tree = CleanDesignTreeNode(id="2:1", name="Details", type=NodeType.CONTAINER)

    responses, warnings = await generate_destination_screens(
        llm,
        routes=routes,
        current_feature="onboarding",
        frame_index={},
        tokens=DesignTokens(),
        asset_manifest=[],
        navigation_hints=[],
        published_styles=None,
        components=None,
        routing_enabled=True,
        destination_trees={"details": prebuilt_tree},
        destination_widget_hints={"details": ["Extract card widget"]},
    )

    assert "details" in responses
    llm.generate_async.assert_awaited_once()
    assert llm.generate_async.await_args.args[0] is prebuilt_tree
    assert warnings == []


@pytest.mark.asyncio
async def test_generate_destination_screens_reports_warning_on_failure() -> None:
    from figma_flutter_agent.errors import LlmError

    llm = MagicMock()
    llm.generate_async = AsyncMock(side_effect=LlmError("provider failed"))
    routes = build_feature_routes("onboarding", node_id="1:1")
    routes.append(
        RouteDefinition(
            name="details",
            path="/details",
            screen_class="DetailsScreen",
            route_class=route_class_for("DetailsScreen"),
            import_path="../../features/details/details_screen.dart",
            node_id="2:1",
        )
    )

    responses, warnings = await generate_destination_screens(
        llm,
        routes=routes,
        current_feature="onboarding",
        frame_index={
            "2:1": {"id": "2:1", "name": "Details", "type": "FRAME", "children": []},
        },
        tokens=DesignTokens(),
        asset_manifest=[],
        navigation_hints=[],
        published_styles=None,
        components=None,
        routing_enabled=True,
        allow_stubs=True,
    )

    assert responses == {}
    assert any("details" in warning for warning in warnings)
