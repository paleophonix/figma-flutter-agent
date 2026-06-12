"""Prototype animation metadata for optional §21 transition generation."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.transitions import PrototypeTransition

_SUPPORTED_MVP_TYPES = frozenset(
    {
        "DISSOLVE",
        "FADE",
        "SLIDE_IN",
        "SLIDE_OUT",
        "PUSH",
        "MOVE_IN",
        "MOVE_OUT",
        "INSTANT",
    }
)
_POST_MVP_TYPES = frozenset({"SMART_ANIMATE", "SMART", "CUSTOM_ANIMATE"})


def _transition_entry(link: PrototypeLink) -> dict[str, Any]:
    transition = link.transition
    return {
        "sourceNodeId": link.source_node_id,
        "sourceNodeName": link.source_node_name,
        "destinationNodeId": link.destination_node_id,
        "trigger": link.trigger,
        "navigationKind": link.navigation_kind,
        "figmaTransitionType": transition.type if transition else None,
        "flutterTransitionKind": transition.transition_kind if transition else None,
        "durationMs": transition.duration_ms if transition else None,
        "easing": transition.easing if transition else None,
        "flutterCurve": transition.flutter_curve if transition else None,
    }


def collect_animation_suggestions(
    links: list[PrototypeLink],
    *,
    route_transitions: dict[str, PrototypeTransition] | None = None,
) -> list[str]:
    """Non-fatal hints for prototype transitions and animation coverage."""
    suggestions: list[str] = []
    if not links and not route_transitions:
        suggestions.append(
            "No prototype navigation links detected; route transitions and "
            "PrototypeNavigation helpers will not be generated."
        )
        return suggestions

    typed_links = [link for link in links if link.transition is not None]
    if links and not typed_links:
        suggestions.append(
            f"{len(links)} prototype link(s) omit transition metadata; "
            "Flutter navigation will use default platform transitions."
        )

    post_mvp = sorted(
        {
            link.transition.type
            for link in typed_links
            if link.transition is not None and link.transition.type in _POST_MVP_TYPES
        }
    )
    if post_mvp:
        suggestions.append(
            "Post-MVP transition types mapped to scale/fade approximations: "
            + ", ".join(post_mvp)
            + ". Lottie and per-widget micro-animations are not generated."
        )

    unsupported = sorted(
        {
            link.transition.type
            for link in typed_links
            if link.transition is not None
            and link.transition.type not in _SUPPORTED_MVP_TYPES
            and link.transition.type not in _POST_MVP_TYPES
        }
    )
    if unsupported:
        suggestions.append(
            "Unsupported Figma transition types (manual Flutter animation may be required): "
            + ", ".join(unsupported)
        )

    if route_transitions:
        kinds = sorted({item.transition_kind for item in route_transitions.values()})
        suggestions.append(
            f"Router page transitions will be generated for {len(route_transitions)} "
            f"route(s): {', '.join(kinds)}."
        )
    return suggestions


def build_animation_manifest(
    links: list[PrototypeLink],
    *,
    route_transitions: dict[str, PrototypeTransition] | None = None,
    routing_type: str = "none",
) -> dict[str, Any]:
    """Structured animation manifest written to ``.debug`` (spec §21)."""
    route_entries = [
        {
            "routePath": path,
            "flutterTransitionKind": transition.transition_kind,
            "figmaTransitionType": transition.type,
            "durationMs": transition.duration_ms,
            "easing": transition.easing,
            "flutterCurve": transition.flutter_curve,
        }
        for path, transition in sorted((route_transitions or {}).items())
    ]
    return {
        "routingType": routing_type,
        "mvpTransitionTypes": sorted(_SUPPORTED_MVP_TYPES),
        "postMvpNotes": [
            "SMART_ANIMATE approximated as scale+fade",
            "Lottie and implicit widget animations are not auto-generated",
        ],
        "prototypeLinks": [_transition_entry(link) for link in links],
        "routeTransitions": route_entries,
        "suggestions": collect_animation_suggestions(
            links,
            route_transitions=route_transitions,
        ),
    }
