"""Surgical visual refine: extract and replace single-widget Dart snippets."""

from __future__ import annotations

from figma_flutter_agent.tools.ast_sidecar import apply_ast_rules, extract_widget_by_figma_id, replace_widget_by_figma_id


def extract_widget_snippet(screen_code: str, figma_id: str) -> str | None:
    """Extract the ``Positioned`` widget Dart for ``figma_id`` via the AST sidecar.

    Args:
        screen_code: Full screen Dart source.
        figma_id: Figma node id.

    Returns:
        Widget snippet, or ``None`` when not found.
    """
    return extract_widget_by_figma_id(screen_code, figma_id)


def build_surgical_snippets(
    screen_code: str,
    node_ids: list[str],
) -> dict[str, str]:
    """Build figma-id → widget snippet map for surgical LLM refine.

    Args:
        screen_code: Full screen Dart source.
        node_ids: Target Figma node ids.

    Returns:
        Snippets for nodes that were found in ``screen_code``.
    """
    snippets: dict[str, str] = {}
    for node_id in node_ids:
        snippet = extract_widget_snippet(screen_code, node_id)
        if snippet is not None:
            snippets[node_id] = snippet
    return snippets


def apply_surgical_patches(
    screen_code: str,
    patches: dict[str, str],
) -> str:
    """Apply per-node widget replacements to screen Dart source.

    Args:
        screen_code: Original screen source.
        patches: Map of figma node id → replacement widget expression.

    Returns:
        Updated screen source.
    """
    updated = screen_code
    for node_id, replacement in patches.items():
        updated = replace_widget_by_figma_id(updated, node_id, replacement) or updated
    if patches:
        updated = apply_ast_rules(updated, prefer_subprocess=False).source
    return updated
