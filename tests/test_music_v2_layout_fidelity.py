"""Regression tests for music_v2 player chrome layout."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees
from figma_flutter_agent.parser.layout import (
    reconcile_playback_timestamp_row_in_tree,
    reconcile_title_subtitle_stacks_in_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_DUMP_CANDIDATES = (
    _REPO_ROOT.parent / "demo_app" / ".debug" / "processed" / "music_v2_layout.json",
    _REPO_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".debug"
    / "processed"
    / "music_v2_layout.json",
)


def _demo_dump_path() -> Path | None:
    for candidate in _DEMO_DUMP_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _load_demo_tree() -> CleanDesignTreeNode | None:
    dump_path = _demo_dump_path()
    if dump_path is None:
        return None
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _find(node_id: str, node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(node_id, child)
        if found is not None:
            return found
    return None


def _tree_contains_skip_controls(node: CleanDesignTreeNode) -> bool:
    if "skip" in (node.name or "").lower():
        return True
    if node.vector_asset_key in {
        "assets/icons/vector_1_4017.svg",
        "assets/icons/vector_1_4020.svg",
    }:
        return True
    return any(_tree_contains_skip_controls(child) for child in node.children)


def test_prune_cluster_duplicate_preserves_backward_when_right_pinned() -> None:
    """Rewind skip mirrored with ``right`` only must not inherit the forward asset."""
    forward = CleanDesignTreeNode(
        id="skip-fwd",
        name="Skip forward",
        type=NodeType.STACK,
        cluster_id="cluster_0",
        sizing=Sizing(width=39.0, height=39.0),
        stack_placement=StackPlacement(left=247.8, width=39.0, height=39.0),
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
        stack_placement=StackPlacement(right=247.8, width=39.0, height=39.0),
        children=[
            CleanDesignTreeNode(
                id="vec-b",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_back.svg",
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="row",
        name="Controls",
        type=NodeType.STACK,
        sizing=Sizing(width=286.6, height=109.0),
        children=[forward, backward],
    )
    prune_duplicated_cluster_subtrees(root)
    assert backward.children == []
    assert backward.vector_asset_key == "assets/icons/vector_back.svg"


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
    assert title.stack_placement.horizontal == "LEFT_RIGHT"
    assert float(title.stack_placement.width or 0) == pytest.approx(263.7, abs=1.0)
    assert title.stack_placement.left == pytest.approx(0.0, abs=0.5)


def _synthetic_media_controls_stack() -> CleanDesignTreeNode:
    """Timeline row + play cluster (mirrors music_v2 seek duplication pattern)."""
    play_cluster = CleanDesignTreeNode(
        id="play",
        name="Play cluster",
        type=NodeType.STACK,
        sizing=Sizing(width=286.6, height=109.0),
        stack_placement=StackPlacement(left=43.7, top=0.0, width=286.6, height=109.0),
        children=[
            CleanDesignTreeNode(
                id="core",
                name="Core",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=88.0, height=88.0),
                style=NodeStyle(background_color="0xFF3F414E", border_radius=44.0),
                stack_placement=StackPlacement(left=88.8, top=0.0, width=88.0, height=88.0),
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="timeline",
        name="Timeline",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=201.3),
        stack_placement=StackPlacement(left=20.0, top=528.5, width=374.0, height=201.3),
        children=[
            play_cluster,
            CleanDesignTreeNode(
                id="stroke",
                name="Vector 15",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_15.svg",
                sizing=Sizing(width=28.7, height=3.0),
                stack_placement=StackPlacement(left=20.3, top=122.0, width=28.7, height=3.0),
            ),
            CleanDesignTreeNode(
                id="start",
                name="01:30",
                type=NodeType.TEXT,
                text="01:30",
                sizing=Sizing(width=59.0, height=19.3),
                stack_placement=StackPlacement(left=0.0, top=144.3, width=59.0, height=19.3),
            ),
            CleanDesignTreeNode(
                id="end",
                name="45:00",
                type=NodeType.TEXT,
                text="45:00",
                sizing=Sizing(width=59.0, height=19.3),
                stack_placement=StackPlacement(left=333.4, top=161.3, width=59.0, height=19.3),
            ),
            CleanDesignTreeNode(
                id="thumb",
                name="Ellipse 41",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/ellipse_41.svg",
                sizing=Sizing(width=17.0, height=17.0),
                stack_placement=StackPlacement(left=44.5, top=159.1, width=17.0, height=17.0),
            ),
            CleanDesignTreeNode(
                id="track-wide",
                name="Track",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/track.svg",
                sizing=Sizing(width=333.4, height=4.0),
                stack_placement=StackPlacement(left=20.3, top=123.5, width=333.4, height=4.0),
            ),
            CleanDesignTreeNode(
                id="track-narrow",
                name="Thumb vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/thumb.svg",
                sizing=Sizing(width=17.0, height=17.0),
                stack_placement=StackPlacement(left=44.5, top=159.1, width=17.0, height=17.0),
            ),
        ],
    )


def test_media_controls_stack_emits_single_native_slider() -> None:
    from figma_flutter_agent.generator.layout import render_layout_file

    root = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        style=NodeStyle(background_color="0xFFFAF7F2"),
        children=[
            _synthetic_media_controls_stack(),
            CleanDesignTreeNode(
                id="dup-slider",
                name="Progress",
                type=NodeType.SLIDER,
                sizing=Sizing(width=266.9, height=20.0),
                stack_placement=StackPlacement(left=167.1, top=622.1, width=266.9, height=20.0),
            ),
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="music_v2",
        uses_svg=True,
        responsive_enabled=True,
    )["lib/generated/music_v2_layout.dart"]
    assert layout.count("Slider(") == 3
    assert "figma-dup-slider:slider-action" in layout
    assert "width: 374.0" in layout or "width: 374," in layout
    assert "01:30" in layout
    assert "45:00" in layout


def test_partition_hoists_ambient_decor_into_wallpaper_layer() -> None:
    from figma_flutter_agent.generator.background import partition_wallpaper_foreground_tree

    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    render_tree, wallpaper_children, shell = partition_wallpaper_foreground_tree(tree)
    wallpaper_ids = {item.id for item in wallpaper_children}
    assert "1:4031" in wallpaper_ids
    assert "1:4032" in wallpaper_ids
    assert "1:4031" not in {child.id for child in render_tree.children}
    assert shell is None


def test_reconcile_playback_timestamps_aligns_baseline() -> None:
    row = reconcile_playback_timestamp_row_in_tree(_synthetic_media_controls_stack())
    start = _find("start", row)
    end = _find("end", row)
    assert start is not None and end is not None
    assert start.stack_placement is not None and end.stack_placement is not None
    assert start.stack_placement.top == end.stack_placement.top


def test_music_v2_demo_layout_renders_rewind_skip_control() -> None:
    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    if not _tree_contains_skip_controls(tree):
        pytest.skip("demo_app processed dump does not contain skip controls")
    from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.subtree import (
        _subtree_render_root,
        collect_subtree_widget_specs,
        plan_subtree_widget_files,
        replace_extracted_subtree_nodes_with_refs,
    )
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs
    from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree

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
    assert "isForward: false" in combined
    assert "01:30" in combined
    assert "InkWell(" in combined or "GestureDetector(" in combined
    assert combined.count("Slider(") == 1
    assert "isForward: false" in combined or "isForward:false" in combined
    assert "Positioned.fill" in layout
    assert "ellipse_46" in layout or "ellipse_46_1_4031" in layout
    assert "ellipse_41" not in layout
    assert "vector_15" not in layout
    assert "0xFFFAF7F2" not in layout
    assert "width: 331.9" not in layout
    assert "Focus Attention" in layout
