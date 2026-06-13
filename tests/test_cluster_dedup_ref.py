"""Cluster dedup keeps K placements (E0.1) on deterministic and IR paths."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_merged_root_expression
from figma_flutter_agent.generator.ir.tree import default_screen_ir, merge_screen_ir
from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.generator.subtree.render import build_cluster_render_context
from figma_flutter_agent.generator.widget_validation import validate_cluster_widget_extraction
from figma_flutter_agent.parser.dedup.clusters import assign_structural_clusters
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
)
from tests.support.conservation import (
    assert_node_multiset_preserved,
    assert_stack_z_order_preserved,
)


def _icon_instance(node_id: str, *, left: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="IconCluster",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        stack_placement=StackPlacement(
            left=left,
            top=10.0,
            width=24.0,
            height=24.0,
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=20.0, height=20.0),
            )
        ],
    )


def _pruned_icon_row(count: int = 3) -> CleanDesignTreeNode:
    instances = [_icon_instance(f"icon:{index}", left=10.0 + index * 40.0) for index in range(count)]
    root = CleanDesignTreeNode(
        id="stack:screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=80.0),
        children=instances,
    )
    assign_structural_clusters(root)
    prune_generation_layout_tree(root)
    return root


def test_prune_keeps_k_top_level_cluster_siblings() -> None:
    root = _pruned_icon_row(3)
    assert len(root.children) == 3
    assert root.children[0].children
    assert root.children[1].children == []
    assert root.children[2].children == []


def test_cluster_refs_emit_k_positioned_widgets_deterministic_path() -> None:
    root = _pruned_icon_row(3)
    cluster_summary = {
        child.cluster_id: 3
        for child in root.children
        if child.cluster_id is not None
    }
    cluster_classes, cluster_vector_variants = build_cluster_render_context(
        root,
        cluster_summary=cluster_summary,
        min_count=2,
    )
    assert cluster_classes is not None
    normalized = normalize_clean_tree(root)
    body = render_node_body(
        normalized,
        uses_svg=False,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        is_layout_root=True,
    )
    assert body.count("Positioned(") == 3


def test_cluster_refs_emit_k_positioned_widgets_ir_path() -> None:
    root = _pruned_icon_row(3)
    cluster_summary = {
        child.cluster_id: 3
        for child in root.children
        if child.cluster_id is not None
    }
    cluster_classes, cluster_vector_variants = build_cluster_render_context(
        root,
        cluster_summary=cluster_summary,
        min_count=2,
    )
    assert cluster_classes is not None
    merged = merge_screen_ir(root, default_screen_ir(root))
    body = emit_merged_root_expression(
        merged,
        ctx=IrEmitContext(
            uses_svg=False,
            is_layout_root=False,
            responsive_enabled=False,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
        ),
    )
    assert body.count("Positioned(") == 3


def test_fail_duplicate_clusters_gate_accepts_k_layout_refs() -> None:
    root = _pruned_icon_row(3)
    cluster_id = root.children[0].cluster_id
    assert cluster_id is not None
    cluster_summary = {cluster_id: 3}
    cluster_classes, _ = build_cluster_render_context(
        root,
        cluster_summary=cluster_summary,
        min_count=2,
    )
    assert cluster_classes is not None
    class_name = cluster_classes[cluster_id]
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

    spec = collect_cluster_widget_specs(
        root,
        cluster_summary,
        min_count=2,
        widget_suffix="Widget",
    )[0]
    layout_source = render_node_body(
        root,
        uses_svg=False,
        cluster_classes=cluster_classes,
        is_layout_root=True,
    )
    validate_cluster_widget_extraction(
        {
            "lib/generated/screen_layout.dart": layout_source,
            f"lib/widgets/{spec.file_name}.dart": f"class {class_name} {{}}",
        },
        [root],
        cluster_summary,
        min_count=2,
        widget_suffix="Widget",
        enforce_cluster_widgets=False,
        fail_duplicate_clusters=True,
    )
    assert layout_source.count(f"{class_name}(") >= 3


def test_conservation_harness_with_restored_duplicate_instances() -> None:
    root = _pruned_icon_row(4)
    screen_ir = default_screen_ir(root)
    assert_node_multiset_preserved(root, screen_ir)
    merged = merge_screen_ir(
        root,
        ScreenIr(
            root=screen_ir.root,
            stack_child_order=list(reversed([child.id for child in root.children])),
        ),
    )
    assert_stack_z_order_preserved(root, merged)
    assert [child.id for child in merged.children] == [child.id for child in root.children]


def test_shadow_card_fixture_preserves_layout_placement_both_paths() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layouts" / "shadow_card_slot.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(payload)
    child = root.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.width == 331.0
    assert child.stack_placement.height == 94.0
    assert child.stack_placement.left == 22.0
    assert child.stack_placement.right == 22.0
    assert child.style.render_bounds_expand is not None

    normalized = normalize_clean_tree(root)
    normalized_child = normalized.children[0]
    assert normalized_child.stack_placement is not None
    assert normalized_child.stack_placement.left == 22.0
    assert normalized_child.stack_placement.right == 22.0
    assert normalized_child.stack_placement.height == 94.0
    assert normalized_child.style.render_bounds_expand is not None

    layout_body = render_node_body(normalized, uses_svg=False, is_layout_root=True)
    assert "left: 22.0" in layout_body
    assert "right: 22.0" in layout_body
    assert "height: 94.0" in layout_body
    assert "Clip.none" in layout_body
    assert "Padding(left: 22.0" not in layout_body

    merged = merge_screen_ir(normalized, default_screen_ir(normalized))
    ir_body = emit_merged_root_expression(
        merged,
        ctx=IrEmitContext(uses_svg=False, is_layout_root=False, responsive_enabled=False),
    )
    assert "left: 22.0" in ir_body
    assert "right: 22.0" in ir_body
    assert "height: 94.0" in ir_body
    assert "Clip.none" in ir_body
    assert "Padding(left: 22.0" not in ir_body
