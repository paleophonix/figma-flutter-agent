"""Immutable Figma truth tree snapshot vs emit-tree mutations (Track A / A2)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode

VISUAL_PIXEL_FORBIDDEN_MUTATIONS: frozenset[str] = frozenset(
    {
        "reconcile_layout_tree",
        "viewport_clamp",
        "min_touch_paint_expansion",
        "stack_to_column",
        "sectionize",
        "unstack",
        "unpin",
    }
)


@dataclass(frozen=True)
class TruthEmitProvenance:
    """Records one mutation between truth and emit trees."""

    node_id: str
    field: str
    transform: str
    old: object
    new: object


@dataclass(frozen=True)
class TruthEmitPair:
    """Immutable parse truth plus derived emit tree."""

    truth_tree: CleanDesignTreeNode
    emit_tree: CleanDesignTreeNode
    provenance: tuple[TruthEmitProvenance, ...] = ()


def capture_truth_snapshot(tree: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Return an immutable deep copy of the parse-time clean tree."""
    return deep_copy_clean_tree(tree)


def attach_emit_tree(
    truth_tree: CleanDesignTreeNode,
    emit_tree: CleanDesignTreeNode,
    *,
    provenance: tuple[TruthEmitProvenance, ...] = (),
) -> TruthEmitPair:
    """Pair truth baseline with derived emit tree and optional provenance."""
    return TruthEmitPair(
        truth_tree=deep_copy_clean_tree(truth_tree),
        emit_tree=deep_copy_clean_tree(emit_tree),
        provenance=provenance,
    )


def forbidden_mutation(transform: str, *, visual_pixel: bool) -> bool:
    """Return True when ``transform`` is disallowed under visual pixel profile."""
    if not visual_pixel:
        return False
    return transform in VISUAL_PIXEL_FORBIDDEN_MUTATIONS
