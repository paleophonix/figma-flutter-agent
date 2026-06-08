"""Figma semantic hints for scoped repair prompts."""

from __future__ import annotations

import json

from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm
from figma_flutter_agent.llm.repair_scope.locations import AnalyzeErrorLocation
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.figma_keys import parse_figma_key_ids


def find_clean_tree_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = find_clean_tree_node(child, node_id)
        if found is not None:
            return found
    return None


def figma_key_tokens_near_line(source: str, line: int, *, window: int = 15) -> list[str]:
    lines = source.splitlines()
    if not lines:
        return []
    center = max(0, min(line - 1, len(lines) - 1))
    start = max(0, center - window)
    end = min(len(lines), center + window + 1)
    window_source = "\n".join(lines[start:end])
    return parse_figma_key_ids(window_source)


def extract_semantic_hint(
    clean_tree: CleanDesignTreeNode | None,
    *,
    planned_source: str,
    locations: list[AnalyzeErrorLocation],
) -> str:
    """Build Figma structural metadata near the failure site, or ``null``."""
    if clean_tree is None:
        return "null"
    anchor_line = locations[0].line if locations else 1
    tokens = figma_key_tokens_near_line(planned_source, anchor_line)
    if not tokens:
        tokens = parse_figma_key_ids(planned_source)[:5]
    if not tokens:
        return "null"
    nodes: list[dict[str, object]] = []
    for node_id in tokens:
        node = find_clean_tree_node(clean_tree, node_id)
        if node is not None:
            nodes.append(dump_clean_tree_for_llm(node))
    if not nodes:
        return "null"
    return json.dumps(nodes, ensure_ascii=False, indent=2)
