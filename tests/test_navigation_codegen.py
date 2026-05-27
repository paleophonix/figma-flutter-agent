from figma_flutter_agent.generator.navigation_codegen import (
    build_prototype_actions,
    build_route_transitions,
    has_scroll_actions,
)
from figma_flutter_agent.parser.navigation import RouteDefinition, route_class_for
from figma_flutter_agent.parser.prototype import (
    PrototypeLink,
    PrototypeNavigationPlan,
    build_prototype_navigation_plan,
    collect_prototype_links,
    index_frames,
)
from figma_flutter_agent.parser.transitions import parse_prototype_transition
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry, merge_asset_manifests


def test_merge_asset_manifests_deduplicates_by_node_id() -> None:
    base = AssetManifest(
        entries=[AssetManifestEntry(node_id="1:1", asset_path="assets/icons/a.svg", kind="icon")]
    )
    extra = AssetManifest(
        entries=[
            AssetManifestEntry(node_id="1:1", asset_path="assets/icons/duplicate.svg", kind="icon"),
            AssetManifestEntry(node_id="2:2", asset_path="assets/images/b.png", kind="image"),
        ]
    )

    merged = merge_asset_manifests(base, extra)

    assert len(merged.entries) == 2
    assert merged.entries[1].node_id == "2:2"


def test_build_prototype_actions_includes_overlay_method() -> None:
    root = {
        "id": "1:1",
        "name": "Home",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Open Sheet",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "OVERLAY",
                            "destinationId": "2:1",
                        },
                    }
                ],
            }
        ],
    }
    destination = {"id": "2:1", "name": "Sheet", "type": "FRAME"}
    links = collect_prototype_links(root)
    plan = build_prototype_navigation_plan(
        "home",
        frame_index=index_frames(root, destination),
        links=links,
        root_node_id="1:1",
    )

    actions = build_prototype_actions(plan)

    assert len(actions) == 1
    assert actions[0].navigation_kind == "overlay"
    assert actions[0].destination_screen_class.endswith("Screen")


def test_render_prototype_navigation_uses_page_route_builder_for_transitions() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer
    from figma_flutter_agent.parser.transitions import parse_prototype_transition

    transition = parse_prototype_transition(
        {
            "type": "DISSOLVE",
            "duration": 0.25,
            "easing": {"type": "EASE_OUT"},
        }
    )
    assert transition is not None

    actions = build_prototype_actions(
        PrototypeNavigationPlan(
            routes=[
                RouteDefinition(
                    name="home",
                    path="/home",
                    screen_class="HomeScreen",
                    route_class=route_class_for("HomeScreen"),
                    import_path="../../features/home/home_screen.dart",
                    node_id="1:1",
                ),
                RouteDefinition(
                    name="details",
                    path="/details",
                    screen_class="DetailsScreen",
                    route_class=route_class_for("DetailsScreen"),
                    import_path="../../features/details/details_screen.dart",
                    node_id="2:1",
                ),
            ],
            links=[
                PrototypeLink(
                    source_node_id="1:2",
                    source_node_name="Continue",
                    destination_node_id="2:1",
                    trigger="ON_CLICK",
                    navigation_kind="navigate",
                    transition=transition,
                )
            ],
        )
    )

    files = DartRenderer().render_prototype_navigation(actions, "navigator2")
    content = files["lib/core/prototype_navigation.dart"]

    assert "PageRouteBuilder" in content
    assert "Duration(milliseconds: 250)" in content
    assert "Curves.easeOut" in content
    assert "FadeTransition" in content


def test_render_prototype_navigation_generates_modal_helper() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer

    actions = build_prototype_actions(
        PrototypeNavigationPlan(
            routes=[
                RouteDefinition(
                    name="home",
                    path="/home",
                    screen_class="HomeScreen",
                    route_class=route_class_for("HomeScreen"),
                    import_path="../../features/home/home_screen.dart",
                    node_id="1:1",
                ),
                RouteDefinition(
                    name="sheet",
                    path="/sheet",
                    screen_class="SheetScreen",
                    route_class=route_class_for("SheetScreen"),
                    import_path="../../features/sheet/sheet_screen.dart",
                    node_id="2:1",
                ),
            ],
            links=[
                PrototypeLink(
                    source_node_id="1:2",
                    source_node_name="Open Sheet",
                    destination_node_id="2:1",
                    trigger="ON_CLICK",
                    navigation_kind="overlay",
                )
            ],
        )
    )

    files = DartRenderer().render_prototype_navigation(actions, "go_router")

    content = files["lib/core/prototype_navigation.dart"]
    assert "showModalBottomSheet" in content
    assert "SheetScreen" in content
    assert "context.push" not in content


def test_build_route_transitions_maps_destination_paths() -> None:
    transition = parse_prototype_transition(
        {
            "type": "DISSOLVE",
            "duration": 0.2,
            "easing": {"type": "EASE_OUT"},
        }
    )
    assert transition is not None

    plan = PrototypeNavigationPlan(
        routes=[
            RouteDefinition(
                name="home",
                path="/home",
                screen_class="HomeScreen",
                route_class=route_class_for("HomeScreen"),
                import_path="../../features/home/home_screen.dart",
                node_id="1:1",
            ),
            RouteDefinition(
                name="details",
                path="/details",
                screen_class="DetailsScreen",
                route_class=route_class_for("DetailsScreen"),
                import_path="../../features/details/details_screen.dart",
                node_id="2:1",
            ),
        ],
        links=[
            PrototypeLink(
                source_node_id="1:2",
                source_node_name="Continue",
                destination_node_id="2:1",
                trigger="ON_CLICK",
                navigation_kind="navigate",
                transition=transition,
            )
        ],
    )

    route_transitions = build_route_transitions(plan)

    assert route_transitions["/details"] is transition


def test_render_router_files_uses_custom_transition_page_for_go_router() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer
    from figma_flutter_agent.parser.transitions import parse_prototype_transition

    transition = parse_prototype_transition(
        {
            "type": "SLIDE_IN",
            "duration": 0.3,
            "easing": {"type": "EASE_IN_AND_OUT"},
        }
    )
    assert transition is not None
    routes = [
        RouteDefinition(
            name="home",
            path="/home",
            screen_class="HomeScreen",
            route_class=route_class_for("HomeScreen"),
            import_path="../../features/home/home_screen.dart",
            node_id="1:1",
        ),
        RouteDefinition(
            name="details",
            path="/details",
            screen_class="DetailsScreen",
            route_class=route_class_for("DetailsScreen"),
            import_path="../../features/details/details_screen.dart",
            node_id="2:1",
        ),
    ]

    files = DartRenderer().render_router_files(
        routes,
        "go_router",
        route_transitions={"/details": transition},
    )
    content = files["lib/core/app_router.dart"]

    assert "CustomTransitionPage" in content
    assert "milliseconds: 300" in content
    assert "SlideTransition" in content


def test_render_prototype_navigation_generates_swap_and_scroll_helpers() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer

    actions = build_prototype_actions(
        PrototypeNavigationPlan(
            routes=[
                RouteDefinition(
                    name="home",
                    path="/home",
                    screen_class="HomeScreen",
                    route_class=route_class_for("HomeScreen"),
                    import_path="../../features/home/home_screen.dart",
                    node_id="1:1",
                ),
                RouteDefinition(
                    name="checkout",
                    path="/checkout",
                    screen_class="CheckoutScreen",
                    route_class=route_class_for("CheckoutScreen"),
                    import_path="../../features/checkout/checkout_screen.dart",
                    node_id="3:1",
                ),
            ],
            links=[
                PrototypeLink(
                    source_node_id="1:3",
                    source_node_name="Swap State",
                    destination_node_id="3:1",
                    trigger="ON_CLICK",
                    navigation_kind="swap",
                ),
                PrototypeLink(
                    source_node_id="1:4",
                    source_node_name="Jump To Summary",
                    destination_node_id="3:1",
                    trigger="ON_CLICK",
                    navigation_kind="scroll",
                ),
            ],
        )
    )

    assert has_scroll_actions(actions) is True
    files = DartRenderer().render_prototype_navigation(actions, "go_router")
    navigation = files["lib/core/prototype_navigation.dart"]
    scroll_targets = files["lib/core/prototype_scroll_targets.dart"]

    assert "context.replace('/checkout')" in navigation
    assert "PrototypeScrollTargets.scrollTo" in navigation
    assert "class PrototypeScrollTargets" in scroll_targets


def test_render_router_files_uses_custom_route_for_auto_route() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer

    transition = parse_prototype_transition(
        {
            "type": "DISSOLVE",
            "duration": 0.25,
            "easing": {"type": "EASE_OUT"},
        }
    )
    assert transition is not None
    routes = [
        RouteDefinition(
            name="home",
            path="/home",
            screen_class="HomeScreen",
            route_class=route_class_for("HomeScreen"),
            import_path="../../features/home/home_screen.dart",
            node_id="1:1",
        ),
        RouteDefinition(
            name="details",
            path="/details",
            screen_class="DetailsScreen",
            route_class=route_class_for("DetailsScreen"),
            import_path="../../features/details/details_screen.dart",
            node_id="2:1",
        ),
    ]

    files = DartRenderer().render_router_files(
        routes,
        "auto_route",
        route_transitions={"/details": transition},
    )
    content = files["lib/core/app_router.dart"]

    assert "CustomRoute" in content
    assert "DetailsRoute.page" in content
    assert "FadeTransition" in content


def test_render_prototype_navigation_uses_auto_route_router_api() -> None:
    from figma_flutter_agent.generator.renderer import DartRenderer

    actions = build_prototype_actions(
        PrototypeNavigationPlan(
            routes=[
                RouteDefinition(
                    name="home",
                    path="/home",
                    screen_class="HomeScreen",
                    route_class=route_class_for("HomeScreen"),
                    import_path="../../features/home/home_screen.dart",
                    node_id="1:1",
                ),
                RouteDefinition(
                    name="details",
                    path="/details",
                    screen_class="DetailsScreen",
                    route_class=route_class_for("DetailsScreen"),
                    import_path="../../features/details/details_screen.dart",
                    node_id="2:1",
                ),
            ],
            links=[
                PrototypeLink(
                    source_node_id="1:2",
                    source_node_name="Continue",
                    destination_node_id="2:1",
                    trigger="ON_CLICK",
                    navigation_kind="navigate",
                )
            ],
        )
    )

    content = DartRenderer().render_prototype_navigation(actions, "auto_route")[
        "lib/core/prototype_navigation.dart"
    ]

    assert "import 'app_router.dart';" in content
    assert "context.router.push(const DetailsRoute())" in content
    assert "features/details/details_screen.dart" not in content
