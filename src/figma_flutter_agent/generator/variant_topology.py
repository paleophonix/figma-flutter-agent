"""Variant topology signature for component configuration (WP-3)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_TOPOLOGY_SIGNATURE_THRESHOLD = 0.85


def _topology_signature(node: CleanDesignTreeNode) -> frozenset[str]:
    """Structural signature: node types + child depth paths (no copy text)."""
    tokens: set[str] = set()

    def visit(current: CleanDesignTreeNode, depth: int) -> None:
        tokens.add(f"{depth}:{current.type.value}")
        for index, child in enumerate(current.children):
            visit(child, depth + 1)
            tokens.add(f"{depth}->{index}:{child.type.value}")

    visit(node, 0)
    return frozenset(tokens)


def jaccard_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    """Return Jaccard index between two topology signatures."""
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


@dataclass(frozen=True)
class VariantTopologyDecision:
    """Outcome of comparing variant subtrees."""

    should_split: bool
    similarity: float
    left_id: str
    right_id: str


def compare_variant_topology(
    left: CleanDesignTreeNode,
    right: CleanDesignTreeNode,
) -> VariantTopologyDecision:
    """Return whether two variant roots should split (INV-V1 / INV-SIGNATURE)."""
    sig_left = _topology_signature(left)
    sig_right = _topology_signature(right)
    similarity = jaccard_similarity(sig_left, sig_right)
    return VariantTopologyDecision(
        should_split=similarity < _TOPOLOGY_SIGNATURE_THRESHOLD,
        similarity=similarity,
        left_id=left.id,
        right_id=right.id,
    )


def validate_variant_signature(
    variants: list[CleanDesignTreeNode],
) -> list[VariantTopologyDecision]:
    """Fail-loud pairwise topology drift check for variant clusters."""
    decisions: list[VariantTopologyDecision] = []
    component_variants = [v for v in variants if v.type != NodeType.TEXT]
    for index, left in enumerate(component_variants):
        for right in component_variants[index + 1 :]:
            decision = compare_variant_topology(left, right)
            if decision.should_split:
                decisions.append(decision)
    return decisions
