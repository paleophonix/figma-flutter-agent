"""Widget class naming helpers for extraction."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case
from figma_flutter_agent.schemas import CleanDesignTreeNode


def fallback_class_name(node: CleanDesignTreeNode, widget_suffix: str) -> str:
    """Build a PascalCase widget class name from a node layer name."""
    stem = to_pascal_case(node.name) or "Extracted"
    if stem.endswith(widget_suffix):
        return stem
    return f"{stem}{widget_suffix}"


def snake_case_class_name(class_name: str) -> str:
    """Return snake_case file stem for a widget class name."""
    return to_snake_case(class_name)
