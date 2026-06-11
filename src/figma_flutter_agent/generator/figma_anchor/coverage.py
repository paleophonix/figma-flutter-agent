"""Coverage checks for Figma anchors and copied text."""

from __future__ import annotations

from figma_flutter_agent.generator.figma_anchor.keys import figma_key_token
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse, NodeType


def _figma_key_present(source: str, node_id: str) -> bool:
    """Return True when ``source`` already references ``node_id`` as a Figma anchor."""
    token = figma_key_token(node_id)
    colon_token = f"figma-{node_id}"
    underscore_id = node_id.replace(":", "_")
    return token in source or colon_token in source or underscore_id in source


def _subtree_text_copies(node: CleanDesignTreeNode) -> tuple[str, ...]:
    copies: list[str] = []
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text:
            copies.append(text)
    for child in node.children:
        copies.extend(_subtree_text_copies(child))
    return tuple(copies)


def _text_copy_present(copy: str, source: str) -> bool:
    if not copy:
        return False
    if f"'{copy}'" in source or f'"{copy}"' in source:
        return True
    return f"label: '{copy}'" in source or f'label: "{copy}"' in source


def _layout_node_covered_in_sources(
    node_id: str,
    node: CleanDesignTreeNode | None,
    *sources: str,
) -> bool:
    """Return True when Figma anchors or label copy already exist in companion Dart."""
    combined = "\n".join(sources)
    if _figma_key_present(combined, node_id):
        return True
    if node is None:
        return False
    return any(_text_copy_present(copy, combined) for copy in _subtree_text_copies(node))


def _layout_node_covered_in_companion_sources(
    node_id: str,
    node: CleanDesignTreeNode | None,
    *companion_sources: str,
) -> bool:
    """Return True when extracted widgets already own this node (not the screen stub)."""
    if not companion_sources:
        return False
    return _layout_node_covered_in_sources(node_id, node, *companion_sources)


def companion_dart_sources_for_layout_inject(
    planned_files: dict[str, str],
    *,
    layout_path: str | None = None,
    generation: FlutterGenerationResponse | None = None,
) -> tuple[str, ...]:
    """Collect widget / feature Dart bodies used to detect LLM coverage before layout inject."""
    sources: list[str] = []
    for path, content in planned_files.items():
        if not path.endswith(".dart"):
            continue
        if layout_path and path.replace("\\", "/") == layout_path.replace("\\", "/"):
            continue
        normalized = path.replace("\\", "/")
        if normalized.startswith(("lib/widgets/", "lib/features/")):
            sources.append(content)
    if generation is not None:
        sources.extend(
            widget.resolved_code()
            for widget in generation.extracted_widgets
            if widget.resolved_code()
        )
    return tuple(sources)
