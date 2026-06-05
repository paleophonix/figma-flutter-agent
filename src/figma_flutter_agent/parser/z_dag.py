"""Unified Z-order DAG for stack paint and validation (WP-6)."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.parser.overlap_sweep import OverlapPair, sibling_overlap_pairs
from figma_flutter_agent.parser.z_bands import _is_interactive, _is_presentational, semantic_z_band
from figma_flutter_agent.schemas import CleanDesignTreeNode

_MAX_TOPO_PASSES = 4096


@dataclass(frozen=True)
class ZDagEdge:
    """Directed edge: ``before`` must paint below ``after``."""

    before_id: str
    after_id: str
    reason: str


def build_z_dag_edges(children: list[CleanDesignTreeNode]) -> list[ZDagEdge]:
    """Build overlap + semantic Z constraints for stack siblings."""
    if len(children) < 2:
        return []
    edges: list[ZDagEdge] = []
    by_id = {child.id: child for child in children}
    for pair in sibling_overlap_pairs(children):
        first = by_id.get(pair.first_id)
        second = by_id.get(pair.second_id)
        if first is None or second is None:
            continue
        for decor, interactive in ((first, second), (second, first)):
            if _is_presentational(decor) and _is_interactive(interactive):
                edges.append(
                    ZDagEdge(
                        before_id=decor.id,
                        after_id=interactive.id,
                        reason="decor_below_interactive",
                    )
                )
    return edges


def _stable_index_order(children: list[CleanDesignTreeNode]) -> list[CleanDesignTreeNode]:
    indexed = list(enumerate(children))
    indexed.sort(key=lambda item: (semantic_z_band(item[1]), item[0]))
    return [child for _, child in indexed]


def _topo_sort_with_edges(
    children: list[CleanDesignTreeNode],
    edges: list[ZDagEdge],
) -> list[CleanDesignTreeNode]:
    """Stable topological sort honoring semantic band then overlap edges."""
    if len(children) < 2:
        return children
    order = _stable_index_order(children)
    by_id = {child.id: child for child in order}
    id_index = {child.id: index for index, child in enumerate(order)}

    passes = 0
    changed = True
    while changed and passes < _MAX_TOPO_PASSES:
        changed = False
        passes += 1
        for edge in edges:
            before_idx = id_index.get(edge.before_id)
            after_idx = id_index.get(edge.after_id)
            if before_idx is None or after_idx is None:
                continue
            if before_idx > after_idx:
                node = by_id[edge.before_id]
                order.pop(before_idx)
                order.insert(after_idx, node)
                id_index = {child.id: index for index, child in enumerate(order)}
                changed = True
                break
    if passes >= _MAX_TOPO_PASSES and changed:
        logger.warning(
            "Z-DAG topological sort hit cycle or pass limit; using stable sibling-index fallback"
        )
        return _stable_index_order(children)
    return order


def z_dag_sort(children: list[CleanDesignTreeNode]) -> list[CleanDesignTreeNode]:
    """Return stack children in unified Z-DAG paint order."""
    edges = build_z_dag_edges(children)
    return _topo_sort_with_edges(children, edges)


def demote_overlapping_occluders(
    children: list[CleanDesignTreeNode],
) -> list[CleanDesignTreeNode]:
    """Reorder siblings so presentational occluders paint below interactives."""
    return z_dag_sort(children)


def ghost_occlusion_violations(
    children: list[CleanDesignTreeNode],
) -> list[OverlapPair]:
    """Return overlap pairs where decor paints above interactive in **current** order."""
    if len(children) < 2:
        return []
    by_id = {child.id: child for child in children}
    violations: list[OverlapPair] = []
    for pair in sibling_overlap_pairs(children):
        first = by_id.get(pair.first_id)
        second = by_id.get(pair.second_id)
        if first is None or second is None:
            continue
        idx_first = next(i for i, c in enumerate(children) if c.id == pair.first_id)
        idx_second = next(i for i, c in enumerate(children) if c.id == pair.second_id)
        later = first if idx_first > idx_second else second
        earlier = second if idx_first > idx_second else first
        if _is_interactive(earlier) and _is_presentational(later):
            violations.append(pair)
    return violations
