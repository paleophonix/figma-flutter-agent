"""Deterministic gates for reusable widget inference candidates."""

from __future__ import annotations

import re

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction.eligibility import (
    is_eligible_extraction_candidate,
)
from figma_flutter_agent.generator.widget_extraction.policy import (
    effective_ai_reusable_limits,
    effective_min_count,
)
from figma_flutter_agent.generator.widget_extraction.scorer import (
    ScoredCandidate,
    score_static_candidates,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.schemas.reusable_candidates import ReusableWidgetCandidate

_PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def resolve_node_by_id(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    """Return the first node with ``node_id`` in ``root`` subtree."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.id == node_id:
            return node
        stack.extend(node.children)
    return None


def normalize_widget_class_name(name: str, *, widget_suffix: str) -> str | None:
    """Return PascalCase widget class name or None when invalid."""
    stem = name.strip()
    if not stem:
        return None
    class_name = stem if stem.endswith(widget_suffix) else f"{stem}{widget_suffix}"
    if not _PASCAL_RE.match(class_name.removesuffix(widget_suffix) or class_name):
        return None
    return class_name


def passes_static_gate(
    *,
    config: WidgetExtractionConfig,
    root: CleanDesignTreeNode,
    node_id: str,
    legacy_min_count: int = 2,
) -> bool:
    """Return True when a node has sufficient static scorer support."""
    node = resolve_node_by_id(root, node_id)
    if node is None:
        return False
    min_score = config.auto_reusable_min_score * 0.8
    for candidate in score_static_candidates(
        root,
        config=config,
        legacy_min_count=legacy_min_count,
    ):
        if candidate.node.id == node_id and candidate.score >= min_score:
            return True
        if node_id in candidate.similar_node_ids and candidate.score >= min_score:
            return True
    return False


def gate_reusable_candidate(
    candidate: ReusableWidgetCandidate,
    *,
    config: WidgetExtractionConfig,
    root: CleanDesignTreeNode,
    widget_suffix: str,
    claimed_class_names: set[str],
    claimed_node_ids: set[str],
    legacy_min_count: int = 2,
) -> CleanDesignTreeNode | None:
    """Validate an LLM reusable candidate; return resolved node or None."""
    min_confidence, _ = effective_ai_reusable_limits(config)
    if candidate.confidence < min_confidence:
        return None
    node = resolve_node_by_id(root, candidate.node_id)
    if node is None or node.id in claimed_node_ids:
        return None
    if not is_eligible_extraction_candidate(node):
        return None
    class_name = normalize_widget_class_name(candidate.widget_name, widget_suffix=widget_suffix)
    if class_name is None or class_name in claimed_class_names:
        return None
    min_count = effective_min_count(config, legacy_min_count=legacy_min_count)
    if config.ai_reusable.require_evidence:
        similar = list(candidate.evidence.similar_nodes if candidate.evidence else [])
        if candidate.node_id not in similar:
            similar.append(candidate.node_id)
        if len(similar) < min_count and not passes_static_gate(
            config=config,
            root=root,
            node_id=candidate.node_id,
            legacy_min_count=legacy_min_count,
        ):
            return None
    if config.ai_reusable.require_static_gate and not passes_static_gate(
        config=config,
        root=root,
        node_id=candidate.node_id,
        legacy_min_count=legacy_min_count,
    ):
        return None
    return node


def gate_scored_candidate(
    candidate: ScoredCandidate,
    *,
    config: WidgetExtractionConfig,
    root: CleanDesignTreeNode,
    widget_suffix: str,
    claimed_class_names: set[str],
    claimed_node_ids: set[str],
    legacy_min_count: int = 2,
) -> CleanDesignTreeNode | None:
    """Validate a static scored candidate; return node or None."""
    _ = legacy_min_count
    if candidate.score < config.auto_reusable_min_score:
        return None
    node = candidate.node
    if node.id in claimed_node_ids:
        return None
    if not is_eligible_extraction_candidate(node):
        return None
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    stem = to_pascal_case(node.name) or "Extracted"
    class_name = stem if stem.endswith(widget_suffix) else f"{stem}{widget_suffix}"
    if class_name in claimed_class_names:
        return None
    if config.ai_reusable.require_evidence and len(candidate.similar_node_ids) < config.min_count:
        return None
    if not resolve_node_by_id(root, node.id):
        return None
    return node
