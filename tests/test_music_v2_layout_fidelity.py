"""Regression tests for music_v2 player chrome layout."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from figma_flutter_agent.parser.dedup import prune_duplicated_cluster_subtrees
from figma_flutter_agent.parser.layout import reconcile_title_subtitle_stacks_in_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_DUMP = (
    _REPO_ROOT.parent / "demo_app" / ".figma_debug" / "processed" / "music_v2_layout.json"
)


def _load_demo_tree() -> CleanDesignTreeNode | None:
    if not _DEMO_DUMP.is_file():
        return None
    payload = json.loads(_DEMO_DUMP.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _find(node_id: str, node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(node_id, child)
        if found is not None:
            return found
    return None


def test_prune_cluster_duplicate_preserves_backward_vector_asset() -> None:
    vector_child = CleanDesignTreeNode(
        id="vec-b",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/vector_back.svg",
    )
    forward = CleanDesignTreeNode(
        id="skip-fwd",
        name="Skip forward",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=39.0, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="vec-f",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_fwd.svg",
            )
        ],
    )
    backward = CleanDesignTreeNode(
        id="skip-back",
        name="Skip back",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=39.0, height=39.0),
        children=[vector_child],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Controls",
        type=NodeType.STACK,
        children=[forward, backward],
    )
    prune_duplicated_cluster_subtrees(root)
    assert backward.children == []
    assert backward.vector_asset_key == "assets/icons/vector_back.svg"


def test_reconcile_title_subtitle_stacks_separates_lines() -> None:
    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    group = _find("1:4028", tree)
    assert group is not None
    updated = reconcile_title_subtitle_stacks_in_tree(group)
    title = _find("1:4029", updated)
    subtitle = _find("1:4030", updated)
    assert title is not None and subtitle is not None
    assert title.stack_placement is not None
    assert subtitle.stack_placement is not None
    title_bottom = (title.stack_placement.top or 0) + (title.stack_placement.height or 0)
    assert (subtitle.stack_placement.top or 0) >= title_bottom - 0.5


def test_music_v2_demo_layout_renders_rewind_skip_control() -> None:
    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
    from figma_flutter_agent.generator.layout_renderer import render_layout_file
    from figma_flutter_agent.generator.subtree_widgets import (
        _subtree_render_root,
        collect_subtree_widget_specs,
        plan_subtree_widget_files,
        replace_extracted_subtree_nodes_with_refs,
    )
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs
    from figma_flutter_agent.parser.dedup import prune_generation_layout_tree

    cluster_summary: dict[str, int] = defaultdict(int)

    def _count_clusters(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            cluster_summary[node.cluster_id] += 1
        for child in node.children:
            _count_clusters(child)

    subtree_specs = collect_subtree_widget_specs(tree, widget_suffix="Widget")
    replace_extracted_subtree_nodes_with_refs(tree, subtree_specs)
    prune_generation_layout_tree(tree, extracted_subtree_node_ids=frozenset())
    cluster_summary.clear()
    _count_clusters(tree)
    cluster_specs = collect_cluster_widget_specs(
        tree,
        dict(cluster_summary),
        widget_suffix="Widget",
    )
    variant_trees = [tree]
    variant_trees.extend(_subtree_render_root(spec.representative) for spec in subtree_specs)
    cluster_variants = collect_cluster_vector_variants(
        variant_trees,
        {spec.cluster_id: spec.representative for spec in cluster_specs},
    )
    planned: dict[str, str] = {}
    if subtree_specs:
        planned, _ = plan_subtree_widget_files(
            planned,
            subtree_specs,
            project_dir=None,
            uses_svg=True,
            cluster_classes={spec.cluster_id: spec.class_name for spec in cluster_specs},
            cluster_vector_variants=cluster_variants,
            clean_tree=tree,
        )
    widget_imports = sorted({spec.file_name for spec in subtree_specs})
    files = render_layout_file(
        tree,
        feature_name="music_v2",
        uses_svg=True,
        cluster_classes={spec.cluster_id: spec.class_name for spec in cluster_specs},
        cluster_vector_variants=cluster_variants,
        widget_imports=widget_imports,
    )
    layout = files["lib/generated/music_v2_layout.dart"]
    widgets = "\n".join(planned.values())
    combined = layout + widgets
    assert "SizedBox.shrink()" not in combined
    assert "vector_1_4020.svg" in combined
    assert "01:30" in combined
    assert "InkWell(" in combined or "GestureDetector(" in combined
