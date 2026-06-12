"""Fidelity promotion evidence from classified semantic kinds per fixture screen."""

from __future__ import annotations

from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry, load_layout_tree
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.corpus import iter_semantic_ir_nodes
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas.ir import WidgetIrKind


def classified_semantic_kinds_for_entry(entry: ScreenFixtureEntry) -> frozenset[WidgetIrKind]:
    """Return semantic kinds actually classified on a manifest screen layout.

    Args:
        entry: Screen fixture manifest entry.

    Returns:
        Set of ``WidgetIrKind`` values present in the classified screen IR.
    """
    clean_tree = load_layout_tree(entry)
    screen_ir = default_screen_ir(clean_tree)
    updated_ir, _report = classify_screen_ir(screen_ir, clean_tree)
    hits = iter_semantic_ir_nodes(updated_ir.root, kinds=SEMANTIC_IR_KINDS)
    return frozenset(kind for _figma_id, kind in hits)
