"""Figma prototype reaction parsing for navigation generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from figma_flutter_agent.parser.navigation import (
    RouteDefinition,
    build_feature_routes,
    route_class_for,
)
from figma_flutter_agent.parser.transitions import PrototypeTransition, parse_prototype_transition

NavigationKind = Literal["navigate", "overlay", "swap", "scroll"]
_SUPPORTED_NAVIGATION = frozenset({"NAVIGATE", "NAVIGATE_TO", "OVERLAY", "SWAP", "SCROLL_TO"})


@dataclass(frozen=True)
class PrototypeLink:
    """Single prototype interaction that navigates to another frame."""

    source_node_id: str
    source_node_name: str
    destination_node_id: str
    trigger: str
    navigation_kind: NavigationKind = "navigate"
    transition: PrototypeTransition | None = None


@dataclass
class PrototypeNavigationPlan:
    """Navigation routes and prototype edges discovered in a Figma file."""

    routes: list[RouteDefinition] = field(default_factory=list)
    links: list[PrototypeLink] = field(default_factory=list)
    initial_route: RouteDefinition | None = None


def index_frames(*roots: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index frame-like nodes by id across one or more Figma subtrees."""
    frames: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        node_type = node.get("type")
        if node_type in {"FRAME", "COMPONENT", "SECTION"}:
            frames[node["id"]] = node
        for child in node.get("children") or []:
            walk(child)

    for root in roots:
        if root:
            walk(root)
    return frames


def _normalize_navigation_kind(raw_navigation: str | None) -> NavigationKind | None:
    if not raw_navigation:
        return None
    normalized = raw_navigation.upper()
    if normalized in {"NAVIGATE", "NAVIGATE_TO"}:
        return "navigate"
    if normalized == "OVERLAY":
        return "overlay"
    if normalized == "SWAP":
        return "swap"
    if normalized == "SCROLL_TO":
        return "scroll"
    return None


def _iter_node_actions(reaction: dict[str, Any]) -> list[dict[str, Any]]:
    """Return NODE actions from a reaction, supporting legacy and multi-action formats."""
    actions = reaction.get("actions")
    if isinstance(actions, list):
        node_actions = [action for action in actions if action.get("type") == "NODE"]
        if node_actions:
            return node_actions
    action = reaction.get("action")
    if isinstance(action, dict) and action.get("type") == "NODE":
        return [action]
    return []


def collect_prototype_links(root: dict[str, Any]) -> list[PrototypeLink]:
    """Collect prototype navigation links from a Figma subtree."""
    links: list[PrototypeLink] = []

    def walk(node: dict[str, Any]) -> None:
        node_id = node.get("id", "")
        node_name = node.get("name") or node_id
        for reaction in node.get("reactions") or []:
            trigger = (reaction.get("trigger") or {}).get("type") or "UNKNOWN"
            for action in _iter_node_actions(reaction):
                navigation = action.get("navigation")
                if navigation not in _SUPPORTED_NAVIGATION:
                    continue
                navigation_kind = _normalize_navigation_kind(navigation)
                if navigation_kind is None:
                    continue
                destination_id = action.get("destinationId")
                if not destination_id:
                    continue
                links.append(
                    PrototypeLink(
                        source_node_id=node_id,
                        source_node_name=node_name,
                        destination_node_id=destination_id,
                        trigger=trigger,
                        navigation_kind=navigation_kind,
                        transition=parse_prototype_transition(action.get("transition")),
                    )
                )
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return links


def collect_missing_destination_ids(
    links: list[PrototypeLink], frame_index: dict[str, dict[str, Any]]
) -> list[str]:
    """Return destination frame ids that are not yet indexed."""
    missing: list[str] = []
    seen: set[str] = set()
    for link in links:
        destination_id = link.destination_node_id
        if destination_id in frame_index or destination_id in seen:
            continue
        seen.add(destination_id)
        missing.append(destination_id)
    return missing


def build_prototype_navigation_plan(
    feature_name: str,
    *,
    frame_index: dict[str, dict[str, Any]],
    links: list[PrototypeLink],
    root_node_id: str | None = None,
) -> PrototypeNavigationPlan:
    """Build route definitions from the current feature and prototype destinations."""
    routes = list(build_feature_routes(feature_name, node_id=root_node_id))
    known_names = {route.name for route in routes}

    for link in links:
        destination = frame_index.get(link.destination_node_id)
        if destination is None:
            continue
        destination_name = _frame_feature_name(destination.get("name") or link.destination_node_id)
        if destination_name in known_names:
            continue
        routes.append(_route_from_frame(destination_name, destination))
        known_names.add(destination_name)

    initial_route = routes[0] if routes else None
    return PrototypeNavigationPlan(routes=routes, links=links, initial_route=initial_route)


def build_navigation_hints(plan: PrototypeNavigationPlan) -> list[str]:
    """Convert prototype links into LLM-readable navigation hints."""
    route_by_node_id = {route.node_id: route for route in plan.routes if route.node_id is not None}
    hints: list[str] = []
    for link in plan.links:
        destination_route = route_by_node_id.get(link.destination_node_id)
        if destination_route is None:
            continue
        hint = (
            f"{link.source_node_name} ({link.trigger}, {link.navigation_kind}) -> "
            f"{destination_route.path} ({destination_route.screen_class})"
        )
        if link.navigation_kind == "overlay":
            hint += " [present as modal overlay/bottom sheet, not stack push]"
        elif link.navigation_kind == "swap":
            hint += " [swap variant/state in place]"
        elif link.navigation_kind == "scroll":
            hint += " [scroll to target section]"
        if link.transition is not None:
            hint += (
                f" [transition: {link.transition.type}, "
                f"{link.transition.duration_ms}ms, {link.transition.easing}]"
            )
        hints.append(hint)
    return hints


def _frame_feature_name(raw_name: str) -> str:
    from figma_flutter_agent.parser.navigation import normalize_feature_name

    return normalize_feature_name(raw_name)


def _route_from_frame(feature_name: str, frame: dict[str, Any]) -> RouteDefinition:
    from figma_flutter_agent.parser.navigation import _screen_class_name

    normalized = _frame_feature_name(feature_name)
    screen_class = _screen_class_name(normalized)
    return RouteDefinition(
        name=normalized,
        path=f"/{normalized}",
        screen_class=screen_class,
        route_class=route_class_for(screen_class),
        import_path=f"../../features/{normalized}/{normalized}_screen.dart",
        node_id=frame.get("id"),
    )
