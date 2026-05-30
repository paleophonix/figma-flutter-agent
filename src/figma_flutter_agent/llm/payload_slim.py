"""Slim cleanTree/tokens dicts before LLM user payloads (Stream B)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens

_LLM_STRIP_KEYS: frozenset[str] = frozenset({"cssProperties"})
_LLM_DROP_STRINGS: frozenset[str] = frozenset({"none", "AUTO"})
_TEXT_ONLY_STYLE_KEYS: frozenset[str] = frozenset(
    {
        "textColor",
        "fontSize",
        "fontWeight",
        "textAlign",
        "lineHeight",
        "letterSpacing",
        "fontFamily",
        "fontStyle",
        "glyphTopOffset",
        "glyphHeight",
        "styleName",
    }
)
_TYPES_WITH_TEXT_STYLE: frozenset[str] = frozenset({"TEXT", "BUTTON", "INPUT"})


def model_dump_for_llm(model: BaseModel) -> dict[str, Any]:
    """Serialize a pydantic model for LLM payloads without null/default noise."""
    return model.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
        exclude_defaults=True,
        exclude_unset=True,
    )


def dump_clean_tree_json_for_llm(tree: CleanDesignTreeNode) -> str:
    """JSON string for prompts/debug — same slim rules as ``dump_clean_tree_for_llm``."""
    import json

    return json.dumps(dump_clean_tree_for_llm(tree), ensure_ascii=False, separators=(",", ":"))


def dump_clean_tree_for_llm(tree: CleanDesignTreeNode) -> dict[str, Any]:
    """Serialize a clean tree for LLM prompts with pruning and layout dedup.

    Args:
        tree: Parsed clean design tree.

    Returns:
        JSON-ready dict with nullish fields removed and duplicate cluster subtrees cleared.
    """
    raw = model_dump_for_llm(tree)
    seen_clusters: set[str] = set()
    return slim_clean_tree_dict(raw, seen_clusters)


def dump_tokens_for_llm(tokens: DesignTokens) -> dict[str, Any]:
    """Serialize design tokens as flat maps for LLM prompts.

    Args:
        tokens: Parsed design tokens.

    Returns:
        Pruned token manifest for LLM user payloads.
    """
    return flatten_tokens_dict(model_dump_for_llm(tokens))


def slim_clean_tree_dict(
    node: dict[str, Any],
    seen_clusters: set[str] | None = None,
) -> dict[str, Any]:
    """Prune a clean-tree dict (recursive) with cluster subtree compaction.

    Args:
        node: ``model_dump`` of a clean tree root or subtree.
        seen_clusters: Cluster ids already serialized with full subtrees.

    Returns:
        Pruned tree dict suitable for LLM user payloads.
    """
    clusters = seen_clusters if seen_clusters is not None else set()
    return _slim_tree_node(node, clusters)


def flatten_tokens_dict(tokens: dict[str, Any]) -> dict[str, Any]:
    """Prune empty token sections (``DesignTokens`` uses flat maps).

    Args:
        tokens: ``model_dump`` of ``DesignTokens``.

    Returns:
        Token manifest for LLM user payloads.
    """
    return prune_nullish(tokens)


def prune_nullish(value: Any) -> Any:
    """Recursively drop null, false, default strings, and empty structures.

    Args:
        value: Arbitrary JSON-like value.

    Returns:
        Pruned value; dicts/lists may become omitted at the caller via ``_should_drop``.
    """
    if isinstance(value, dict):
        pruned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _LLM_STRIP_KEYS:
                continue
            cleaned = prune_nullish(item)
            if _should_drop(cleaned):
                continue
            pruned[key] = cleaned
        return pruned
    if isinstance(value, list):
        cleaned_list = [prune_nullish(item) for item in value]
        return [item for item in cleaned_list if not _should_drop(item)]
    return value


def _slim_tree_node(node: dict[str, Any], seen_clusters: set[str]) -> dict[str, Any]:
    """Apply tree-specific rules, cluster pruning, and global nullish cleanup."""
    slimmed = dict(node)

    cluster_id = slimmed.get("clusterId")
    if cluster_id:
        if cluster_id in seen_clusters:
            slimmed["children"] = []
        else:
            seen_clusters.add(cluster_id)

    if _is_zero_padding(slimmed.get("padding")):
        slimmed.pop("padding", None)
    spacing = slimmed.get("spacing")
    if spacing == 0 or spacing == 0.0:
        slimmed.pop("spacing", None)

    style = slimmed.get("style")
    if isinstance(style, dict):
        slimmed["style"] = _prune_style_for_node_type(style, str(slimmed.get("type", "")))

    _drop_redundant_offsets(slimmed)

    children = slimmed.get("children")
    if isinstance(children, list) and children:
        slimmed["children"] = [_slim_tree_node(child, seen_clusters) for child in children]

    return prune_nullish(slimmed)


def _prune_style_for_node_type(style: dict[str, Any], node_type: str) -> dict[str, Any]:
    if node_type in _TYPES_WITH_TEXT_STYLE:
        return style
    trimmed = dict(style)
    for key in _TEXT_ONLY_STYLE_KEYS:
        trimmed.pop(key, None)
    return trimmed


def _drop_redundant_offsets(node: dict[str, Any]) -> None:
    """Remove root offsetX/offsetY when stackPlacement already carries coordinates."""
    if node.get("layoutPositioning") != "ABSOLUTE":
        return
    placement = node.get("stackPlacement")
    if not isinstance(placement, dict):
        return
    node.pop("offsetX", None)
    node.pop("offsetY", None)


def _is_zero_padding(padding: Any) -> bool:
    if not isinstance(padding, dict):
        return False
    sides = ("top", "bottom", "left", "right")
    return all(padding.get(side) in (0, 0.0) for side in sides)


def _should_drop(value: Any) -> bool:
    if value is None or value is False or value == "":
        return True
    if isinstance(value, str) and value in _LLM_DROP_STRINGS:
        return True
    return value == [] or value == {}
