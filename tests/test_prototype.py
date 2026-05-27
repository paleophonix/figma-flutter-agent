from figma_flutter_agent.parser.navigation import build_feature_routes, route_class_for
from figma_flutter_agent.parser.prototype import (
    build_navigation_hints,
    build_prototype_navigation_plan,
    collect_prototype_links,
    index_frames,
)


def test_collect_prototype_links_from_reactions() -> None:
    root = {
        "id": "1:1",
        "name": "Onboarding",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Continue Button",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "NAVIGATE",
                            "destinationId": "2:1",
                        },
                    }
                ],
            }
        ],
    }

    links = collect_prototype_links(root)

    assert len(links) == 1
    assert links[0].destination_node_id == "2:1"
    assert links[0].source_node_name == "Continue Button"
    assert links[0].navigation_kind == "navigate"


def test_collect_prototype_links_parses_transition_metadata() -> None:
    root = {
        "id": "1:1",
        "name": "Home",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Continue",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "actions": [
                            {
                                "type": "NODE",
                                "navigation": "NAVIGATE",
                                "destinationId": "2:1",
                                "transition": {
                                    "type": "DISSOLVE",
                                    "duration": 0.3,
                                    "easing": {"type": "EASE_OUT"},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }

    links = collect_prototype_links(root)

    assert len(links) == 1
    assert links[0].transition is not None
    assert links[0].transition.duration_ms == 300
    assert links[0].transition.flutter_curve == "Curves.easeOut"


def test_build_navigation_hints_includes_transition_metadata() -> None:
    root = {
        "id": "1:1",
        "name": "Home",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Continue",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "NAVIGATE",
                            "destinationId": "2:1",
                            "transition": {
                                "type": "SMART_ANIMATE",
                                "duration": 0.2,
                                "easing": {"type": "EASE_IN_AND_OUT"},
                            },
                        },
                    }
                ],
            }
        ],
    }
    destination = {"id": "2:1", "name": "Details", "type": "FRAME"}
    links = collect_prototype_links(root)
    plan = build_prototype_navigation_plan(
        "home",
        frame_index=index_frames(root, destination),
        links=links,
        root_node_id="1:1",
    )

    hints = build_navigation_hints(plan)
    assert any("transition: SMART_ANIMATE" in hint for hint in hints)


def test_collect_prototype_links_supports_overlay_navigation() -> None:
    root = {
        "id": "1:1",
        "name": "Home",
        "type": "FRAME",
        "children": [
            {
                "id": "1:3",
                "name": "Open Modal",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "OVERLAY",
                            "destinationId": "3:1",
                        },
                    }
                ],
            }
        ],
    }

    links = collect_prototype_links(root)

    assert len(links) == 1
    assert links[0].navigation_kind == "overlay"


def test_build_navigation_hints_describes_overlay_links() -> None:
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

    hints = build_navigation_hints(plan)
    assert any("overlay" in hint and "modal overlay" in hint for hint in hints)


def test_build_prototype_navigation_plan_adds_destination_routes() -> None:
    root = {
        "id": "1:1",
        "name": "Onboarding",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Continue",
                "type": "FRAME",
                "reactions": [
                    {
                        "trigger": {"type": "ON_CLICK"},
                        "action": {
                            "type": "NODE",
                            "navigation": "NAVIGATE",
                            "destinationId": "2:1",
                        },
                    }
                ],
            }
        ],
    }
    destination = {"id": "2:1", "name": "Details Screen", "type": "FRAME"}
    links = collect_prototype_links(root)
    frame_index = index_frames(root, destination)

    plan = build_prototype_navigation_plan(
        "onboarding",
        frame_index=frame_index,
        links=links,
        root_node_id="1:1",
    )

    assert len(plan.routes) == 2
    assert plan.routes[0].name == "onboarding"
    assert plan.routes[1].name == "details_screen"
    assert plan.routes[1].screen_class == "DetailsScreen"
    hints = build_navigation_hints(plan)
    assert any("/details_screen" in hint for hint in hints)


def test_route_class_for_screen() -> None:
    assert route_class_for("OnboardingScreen") == "OnboardingRoute"


def test_build_feature_routes_includes_node_id() -> None:
    routes = build_feature_routes("onboarding", node_id="1:1")
    assert routes[0].node_id == "1:1"
    assert routes[0].route_class == "OnboardingRoute"
