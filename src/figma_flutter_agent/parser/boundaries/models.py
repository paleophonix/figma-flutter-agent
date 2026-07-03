"""Models for render-boundary tree collapse."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RenderBoundaryCollapseResult:
    """Outcome of collapsing render boundaries in a clean tree."""

    collapsed_count: int = 0
    flattened_node_ids: frozenset[str] = field(default_factory=frozenset)
    boundary_node_ids: frozenset[str] = field(default_factory=frozenset)
    decorative_role_map: dict[str, str] = field(default_factory=dict)
