"""Regression: pruned subtrees must appear as widget refs in deterministic layout."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.subtree_widgets import (
    collect_subtree_widget_specs,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.schemas import CleanDesignTreeNode

_DEMO_DUMP = (
    Path(__file__).resolve().parents[2].parent / "demo_app" / ".figma_debug" / "processed"
    / "sign_up_and_sign_in_layout.json"
)


def _load_demo_tree() -> CleanDesignTreeNode | None:
    if not _DEMO_DUMP.is_file():
        return None
    payload = json.loads(_DEMO_DUMP.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def test_sign_up_layout_keeps_extracted_subtree_stubs() -> None:
    tree = _load_demo_tree()
    if tree is None:
        return
    specs = collect_subtree_widget_specs(tree, widget_suffix="Widget")
    assert any(spec.node_id == "1:3677" for spec in specs)
    replace_extracted_subtree_nodes_with_refs(tree, specs)
    prune_generation_layout_tree(tree, extracted_subtree_node_ids=frozenset())
    imports = sorted({spec.file_name for spec in specs})
    files = render_layout_file(
        tree,
        feature_name="sign_up_and_sign_in",
        uses_svg=True,
        widget_imports=imports,
    )
    layout = files["lib/generated/sign_up_and_sign_in_layout.dart"]
    assert "const Group17Widget()" in layout
    assert "const GroupWidget()" in layout
    assert "import 'package:demo_app/widgets/group17_widget.dart'" in layout


def test_sign_up_button_stack_not_single_inkwell_material() -> None:
    tree = _load_demo_tree()
    if tree is None:
        return

    def find(node_id: str, node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if node.id == node_id:
            return node
        for child in node.children:
            found = find(node_id, child)
            if found is not None:
                return found
        return None

    group = find("1:3970", tree)
    assert group is not None
    assert stack_interaction_kind(group) is None
