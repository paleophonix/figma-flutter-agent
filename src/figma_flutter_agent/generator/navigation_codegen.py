"""Deterministic prototype navigation action helpers for generated Dart."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.parser.transitions import PrototypeTransition

_METHOD_NAME = re.compile(r"[^a-zA-Z0-9]+")


@dataclass(frozen=True)
class PrototypeAction:
    """Single generated navigation helper for a prototype link."""

    method_name: str
    source_node_name: str
    destination_screen_class: str
    destination_route_class: str
    destination_import_path: str
    navigation_kind: str
    route_path: str
    transition: PrototypeTransition | None = None
    scroll_target_id: str | None = None
    overlay_style: Literal["sheet", "dialog"] = "sheet"


def _overlay_style(destination_name: str) -> Literal["sheet", "dialog"]:
    """Choose modal bottom sheet vs centered dialog from destination frame name."""
    lowered = destination_name.lower()
    if any(token in lowered for token in ("dialog", "modal", "alert", "popup")):
        return "dialog"
    return "sheet"


def _method_name(source_name: str, navigation_kind: str, destination_name: str) -> str:
    parts = [part for part in _METHOD_NAME.split(source_name) if part]
    source = "".join(part.capitalize() for part in parts) or "Element"
    destination = (
        "".join(part.capitalize() for part in _METHOD_NAME.split(destination_name) if part)
        or "Destination"
    )
    kind = navigation_kind.capitalize()
    return f"{kind}{source}To{destination}"


def build_prototype_actions(plan: PrototypeNavigationPlan) -> list[PrototypeAction]:
    """Build navigation helper metadata from prototype links and routes."""
    route_by_node_id = {route.node_id: route for route in plan.routes if route.node_id is not None}
    actions: list[PrototypeAction] = []
    seen_methods: set[str] = set()

    for link in plan.links:
        destination_route = route_by_node_id.get(link.destination_node_id)
        if destination_route is None:
            continue
        method = _method_name(
            link.source_node_name,
            link.navigation_kind,
            destination_route.name,
        )
        if method in seen_methods:
            suffix = 2
            candidate = f"{method}{suffix}"
            while candidate in seen_methods:
                suffix += 1
                candidate = f"{method}{suffix}"
            method = candidate
        seen_methods.add(method)
        overlay_style: Literal["sheet", "dialog"] = "sheet"
        if link.navigation_kind == "overlay":
            overlay_style = _overlay_style(destination_route.name)
        actions.append(
            PrototypeAction(
                method_name=method,
                source_node_name=link.source_node_name,
                destination_screen_class=destination_route.screen_class,
                destination_route_class=destination_route.route_class,
                destination_import_path=destination_route.import_path,
                navigation_kind=link.navigation_kind,
                route_path=destination_route.path,
                transition=link.transition,
                scroll_target_id=destination_route.name
                if link.navigation_kind == "scroll"
                else None,
                overlay_style=overlay_style,
            )
        )
    return actions


def build_route_transitions(plan: PrototypeNavigationPlan) -> dict[str, PrototypeTransition]:
    """Map route paths to prototype transitions for router page builders."""
    route_by_node_id = {route.node_id: route for route in plan.routes if route.node_id is not None}
    transitions: dict[str, PrototypeTransition] = {}

    for link in plan.links:
        if link.navigation_kind not in {"navigate", "swap"} or link.transition is None:
            continue
        destination_route = route_by_node_id.get(link.destination_node_id)
        if destination_route is None or destination_route.path in transitions:
            continue
        transitions[destination_route.path] = link.transition

    return transitions


def has_scroll_actions(actions: list[PrototypeAction]) -> bool:
    """Return True when any generated action performs in-place scrolling."""
    return any(action.navigation_kind == "scroll" for action in actions)
