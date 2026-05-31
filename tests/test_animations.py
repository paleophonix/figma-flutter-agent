"""Tests for prototype animation manifest (spec §21)."""

from figma_flutter_agent.parser.animations import (
    build_animation_manifest,
    collect_animation_suggestions,
)
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.transitions import PrototypeTransition


def test_collect_animation_suggestions_reports_router_transitions() -> None:
    transition = PrototypeTransition(
        type="DISSOLVE",
        duration_ms=240,
        easing="EASE_OUT",
        flutter_curve="Curves.easeOut",
        transition_kind="fade",
    )
    links = [
        PrototypeLink(
            source_node_id="1:1",
            source_node_name="Button",
            destination_node_id="1:2",
            trigger="ON_CLICK",
            transition=transition,
        )
    ]
    suggestions = collect_animation_suggestions(
        links,
        route_transitions={"/next": transition},
    )
    assert any("Router page transitions" in item for item in suggestions)


def test_build_animation_manifest_lists_prototype_links() -> None:
    transition = PrototypeTransition(
        type="SLIDE_IN",
        duration_ms=300,
        easing="EASE_IN_AND_OUT",
        flutter_curve="Curves.easeInOut",
        transition_kind="slide",
    )
    manifest = build_animation_manifest(
        [
            PrototypeLink(
                source_node_id="1:10",
                source_node_name="CTA",
                destination_node_id="1:20",
                trigger="ON_CLICK",
                transition=transition,
            )
        ],
        routing_type="go_router",
    )
    assert manifest["routingType"] == "go_router"
    assert manifest["prototypeLinks"][0]["figmaTransitionType"] == "SLIDE_IN"
    assert manifest["prototypeLinks"][0]["flutterTransitionKind"] == "slide"
