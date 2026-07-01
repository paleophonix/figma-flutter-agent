"""Deterministic scoring for reusable widget inference candidates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.variant_topology import compare_variant_topology
from figma_flutter_agent.generator.widget_extraction.eligibility import _MIN_SUBTREE_AREA
from figma_flutter_agent.generator.widget_extraction.policy import effective_min_count
from figma_flutter_agent.parser.dedup.signatures import shape_structure_signature
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


@dataclass(frozen=True)
class ScoredCandidate:
    """Static inference candidate with score and similar node ids."""

    node: CleanDesignTreeNode
    score: float
    similar_node_ids: tuple[str, ...]
    source: str = "static"


def score_static_candidates(
    root: CleanDesignTreeNode,
    *,
    config: WidgetExtractionConfig,
    legacy_min_count: int = 2,
) -> list[ScoredCandidate]:
    """Score frame-like subtrees by shape repetition and component-like signals."""
    min_count = effective_min_count(config, legacy_min_count=legacy_min_count)
    by_signature: dict[str, list[CleanDesignTreeNode]] = defaultdict(list)

    def collect(node: CleanDesignTreeNode) -> None:
        if node.children:
            by_signature[shape_structure_signature(node)].append(node)
        for child in node.children:
            collect(child)

    collect(root)
    scored: list[ScoredCandidate] = []
    for nodes in by_signature.values():
        groups = _topology_groups(nodes)
        for group in groups:
            if len(group) < min_count:
                continue
            representative = group[0]
            score = _score_group(group, min_count=min_count)
            if score <= 0.0:
                continue
            similar_ids = tuple(node.id for node in group)
            scored.append(
                ScoredCandidate(
                    node=representative,
                    score=min(1.0, score),
                    similar_node_ids=similar_ids,
                )
            )
    return sorted(scored, key=lambda item: (-item.score, item.node.id))


def _topology_groups(nodes: list[CleanDesignTreeNode]) -> list[list[CleanDesignTreeNode]]:
    groups: list[list[CleanDesignTreeNode]] = []
    for node in nodes:
        matched = False
        for group in groups:
            if not compare_variant_topology(group[0], node).should_split:
                group.append(node)
                matched = True
                break
        if not matched:
            groups.append([node])
    return groups


def _score_group(group: list[CleanDesignTreeNode], *, min_count: int) -> float:
    score = 0.0
    if len(group) >= min_count:
        score += 0.35
    if len(group) >= 3:
        score += 0.1
    representative = group[0]
    if _has_text_and_media(representative):
        score += 0.3
    if representative.component_ref is not None:
        score += 0.2
    if _subtree_area(representative) >= _MIN_SUBTREE_AREA:
        score += 0.1
    return score


def _has_text_and_media(node: CleanDesignTreeNode) -> bool:
    has_text = False
    has_media = False
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == NodeType.TEXT:
            has_text = True
        if current.type in {NodeType.IMAGE, NodeType.VECTOR}:
            has_media = True
        stack.extend(current.children)
        if has_text and has_media:
            return True
    return False


def _subtree_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    if width > 0 and height > 0:
        return float(width) * float(height)
    return 0.0
