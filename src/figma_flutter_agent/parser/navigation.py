"""Navigation route helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SNAKE_CASE = re.compile(r"[^a-zA-Z0-9]+")


def _to_snake_case(value: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    parts = [part for part in _SNAKE_CASE.split(normalized) if part]
    return "_".join(part.lower() for part in parts) or "feature"


@dataclass(frozen=True)
class RouteDefinition:
    """Single generated navigation route."""

    name: str
    path: str
    screen_class: str
    import_path: str
    route_class: str
    node_id: str | None = None


def route_class_for(screen_class: str) -> str:
    """Derive an AutoRoute route class name from a screen class."""
    if screen_class.endswith("Screen"):
        return f"{screen_class[:-6]}Route"
    return f"{screen_class}Route"


def _screen_class_name(feature_name: str) -> str:
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    normalized = _to_snake_case(feature_name)
    if normalized.endswith("_screen"):
        normalized = normalized[: -len("_screen")]
    return f"{to_pascal_case(normalized)}Screen"


def normalize_feature_name(value: str) -> str:
    """Convert arbitrary text to snake_case feature folder name."""
    return _to_snake_case(value)


def build_feature_routes(feature_name: str, *, node_id: str | None = None) -> list[RouteDefinition]:
    """Build default routes for a generated feature screen.

    Args:
        feature_name: Snake-case feature folder name.

    Returns:
        Route definitions for the generated screen.
    """
    normalized = _to_snake_case(feature_name)
    screen_class = _screen_class_name(feature_name)
    return [
        RouteDefinition(
            name=normalized,
            path=f"/{normalized}",
            screen_class=screen_class,
            route_class=route_class_for(screen_class),
            import_path=f"../../features/{normalized}/{normalized}_screen.dart",
            node_id=node_id,
        )
    ]
