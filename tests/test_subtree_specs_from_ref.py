"""Subtree specs must survive layout stub replacement for IR re-plan."""

from __future__ import annotations

from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
    ensure_subtree_widget_planned_files,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def _vector_leaf(node_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(id=node_id, name="Vector", type=NodeType.VECTOR)


def test_collect_subtree_specs_after_stub_replace() -> None:
    vectors = [_vector_leaf(f"1:{3700 + i}") for i in range(10)]
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
        children=vectors,
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        children=[logo],
    )
    specs_before = collect_subtree_widget_specs(root, widget_suffix="Widget")
    replace_extracted_subtree_nodes_with_refs(root, tuple(specs_before))
    specs_after = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert any(spec.class_name == "Group17Widget" for spec in specs_after)


def test_ensure_subtree_widget_planned_files_fills_missing_widgets() -> None:
    vectors = [_vector_leaf(f"1:{3700 + i}") for i in range(10)]
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        children=vectors,
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        children=[logo],
    )
    specs = (
        SubtreeWidgetSpec(
            node_id="1:3665",
            class_name="Group17Widget",
            file_name="group17_widget",
            representative=logo,
            vector_count=10,
        ),
    )
    replace_extracted_subtree_nodes_with_refs(root, specs)
    planned = {
        "lib/generated/sign_up_layout.dart": "const Group17Widget();",
    }
    filled = ensure_subtree_widget_planned_files(
        planned,
        clean_tree=root,
        widget_suffix="Widget",
        uses_svg=False,
    )
    assert "lib/widgets/group17_widget.dart" in filled
    assert "class Group17Widget" in filled["lib/widgets/group17_widget.dart"]


def test_ensure_subtree_skips_rerender_when_widget_already_valid() -> None:
    vectors = [_vector_leaf(f"1:{3700 + i}") for i in range(10)]
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        children=vectors,
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        children=[logo],
    )
    specs = (
        SubtreeWidgetSpec(
            node_id="1:3665",
            class_name="Group17Widget",
            file_name="group17_widget",
            representative=logo,
            vector_count=10,
        ),
    )
    replace_extracted_subtree_nodes_with_refs(root, specs)
    existing_body = """
class Group17Widget extends StatelessWidget {
  const Group17Widget({super.key});
  @override
  Widget build(BuildContext context) {
    return Stack(children: [Text('keep-me')]);
  }
}
"""
    planned = {
        "lib/widgets/group17_widget.dart": existing_body,
    }
    filled = ensure_subtree_widget_planned_files(
        planned,
        clean_tree=root,
        widget_suffix="Widget",
        uses_svg=False,
    )
    assert "keep-me" in filled["lib/widgets/group17_widget.dart"]
