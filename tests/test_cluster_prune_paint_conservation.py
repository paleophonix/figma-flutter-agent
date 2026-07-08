"""Regression tests for LAW-CLUSTER-PRUNE-PAINT-CONSERVATION."""

from copy import deepcopy
from pathlib import Path

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    conservation_node_multiset,
)
from figma_flutter_agent.parser.boundaries.ids import (
    collect_descendant_conservation_ids,
    collect_descendant_figma_ids,
)
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _plus_icon_stack(*, node_id: str, vector_id: str) -> CleanDesignTreeNode:
    """Generic duplicated 28px plus icon component (no exported SVG)."""
    return CleanDesignTreeNode(
        id=node_id,
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[
            CleanDesignTreeNode(
                id=vector_id,
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=14.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )


def test_duplicate_plus_icon_keeps_children_without_vector_asset() -> None:
    """Law: cluster prune must not drop unbound visible vector paint."""
    first = _plus_icon_stack(node_id="plus-1", vector_id="vec-1")
    duplicate = _plus_icon_stack(node_id="plus-2", vector_id="vec-2")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, duplicate],
    )
    prune_generation_layout_tree(root, checkpoint=None)

    assert first.children
    assert duplicate.children
    assert duplicate.children[0].type == NodeType.VECTOR
    assert duplicate.children[0].vector_asset_key is None


def test_duplicate_plus_icon_cp0_parse_preserves_multiset_and_inline_paint() -> None:
    """Blocked prune must not assign flatten metadata while children remain."""
    first = _plus_icon_stack(node_id="plus-1", vector_id="vec-1")
    duplicate = _plus_icon_stack(node_id="plus-2", vector_id="vec-2")
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[first, duplicate],
    )
    before = conservation_node_multiset(deepcopy(root))
    prune_generation_layout_tree(root, checkpoint="CP0_parse")
    after = conservation_node_multiset(root)

    assert before == after
    assert duplicate.children
    assert not duplicate.flatten_figma_node_ids


def test_duplicate_plus_icon_forwards_vector_asset_when_template_bound() -> None:
    """Prune may clear children when drawable vector asset transfers to the cluster root."""
    glyph = CleanDesignTreeNode(
        id="vec-rich",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/plus.svg",
        sizing=Sizing(width=14.0, height=14.0),
    )
    template = CleanDesignTreeNode(
        id="plus-rich",
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[glyph],
    )
    duplicate = CleanDesignTreeNode(
        id="plus-dup",
        name="Icons/28/Plus",
        type=NodeType.STACK,
        cluster_id="component_icons_28_plus",
        component_ref="910:3249",
        sizing=Sizing(width=28.0, height=28.0),
        children=[
            CleanDesignTreeNode(
                id="vec-dup",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=14.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[template, duplicate],
    )
    prune_generation_layout_tree(root, checkpoint=None)

    assert duplicate.vector_asset_key == "assets/icons/plus.svg"
    assert duplicate.children == []


def test_late_image_asset_does_not_unlock_prune_when_child_vectors_remain() -> None:
    """Raster on the cluster root must not clear inline VECTOR children (CP0b idempotency)."""
    vector = CleanDesignTreeNode(
        id="vec-rich",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=14.0, height=14.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
    )
    template = CleanDesignTreeNode(
        id="cutlery-1",
        name="Cutlery",
        type=NodeType.COLUMN,
        cluster_id="component_cutlery",
        sizing=Sizing(width=375.0, height=76.0),
        children=[
            CleanDesignTreeNode(
                id="body-1",
                name="Body",
                type=NodeType.STACK,
                children=[vector],
            )
        ],
    )
    duplicate = CleanDesignTreeNode(
        id="cutlery-2",
        name="Cutlery",
        type=NodeType.COLUMN,
        cluster_id="component_cutlery",
        image_asset_key="assets/images/tableware.png",
        sizing=Sizing(width=375.0, height=76.0),
        children=[
            CleanDesignTreeNode(
                id="body-2",
                name="Body",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="vec-dup",
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=14.0, height=14.0),
                        style=NodeStyle(background_color="0xFFFFFFFF"),
                    )
                ],
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[template, duplicate],
    )
    before = conservation_node_multiset(deepcopy(root))
    prune_generation_layout_tree(root, checkpoint="CP0b_reprune")
    after = conservation_node_multiset(root)

    assert before == after
    assert duplicate.children
    assert duplicate.children[0].children


def test_collect_descendant_conservation_ids_includes_nested_flatten_metadata() -> None:
    """Dedup flatten transfer must re-home ids from nested pruned stubs."""
    nested_flatten_ids = [
        "I4408:44898;1154:7849;1149:9855;1149:9481",
        "I4408:44898;1154:7849;1149:9855;1149:9481;910:3248",
    ]
    pruned_stub = CleanDesignTreeNode(
        id="stepper-pruned",
        name="Stepper",
        type=NodeType.STACK,
        flatten_figma_node_ids=list(nested_flatten_ids),
        children=[],
    )
    parent = CleanDesignTreeNode(
        id="row-duplicate",
        name="OrderRow",
        type=NodeType.STACK,
        children=[pruned_stub],
    )
    assert collect_descendant_figma_ids(parent) == ["stepper-pruned"]
    transferred = collect_descendant_conservation_ids(parent)
    assert transferred[:1] == ["stepper-pruned"]
    assert set(transferred) == {"stepper-pruned", *nested_flatten_ids}


def test_niyama_order_double_cp0b_reprune_preserves_multiset() -> None:
    """Planning runs CP0b twice; nested flatten transfer must keep multiset stable."""
    from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        activate_conservation_session,
    )
    from figma_flutter_agent.generator.subtree import (
        collect_subtree_widget_specs,
        replace_extracted_subtree_nodes_with_refs,
    )
    from figma_flutter_agent.parser.boundaries.assets import (
        resolve_missing_image_asset_keys,
        resolve_pruned_cluster_instance_assets,
        resolve_render_boundary_asset_keys,
    )
    from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
    from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
    from figma_flutter_agent.stages import parse_figma_frame
    from figma_flutter_agent.stages.assets import finalize_screen_assets

    dump = Path("e:/@dev/figma-flutter-agent/.debug/screen/test/niyama_order/raw.json")
    project = Path("e:/@dev/figma-flutter-agent/apps/test")
    if not dump.is_file():
        return

    activate_conservation_session()
    fetch = load_fetch_result_from_dump(dump, file_key="dummy", node_id="4408:44885")
    parsed = parse_figma_frame(fetch)
    exclude = build_screen_frame_exclude_ids(fetch.node_id, set())
    manifest = local_asset_manifest_from_project(
        project,
        exclude_node_ids=exclude,
        clean_tree=parsed.clean_tree,
    )
    finalize_screen_assets(
        project_dir=project,
        clean_tree=parsed.clean_tree,
        destination_trees={},
        manifest=manifest,
        primary_node_id=fetch.node_id,
        destination_node_ids=set(),
    )
    resolve_render_boundary_asset_keys(parsed.clean_tree, project, manifest, strict=False)
    resolve_missing_image_asset_keys(parsed.clean_tree, project)
    resolve_pruned_cluster_instance_assets(parsed.clean_tree, project)

    subtree_specs = collect_subtree_widget_specs(
        parsed.clean_tree,
        widget_suffix="Widget",
    )
    replace_extracted_subtree_nodes_with_refs(parsed.clean_tree, subtree_specs)
    prune_generation_layout_tree(parsed.clean_tree, extracted_subtree_node_ids=frozenset())

    replace_extracted_subtree_nodes_with_refs(parsed.clean_tree, subtree_specs)
    prune_generation_layout_tree(parsed.clean_tree, extracted_subtree_node_ids=frozenset())

    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids

    validate_unique_node_ids(parsed.clean_tree)


def test_hydration_rewrites_component_instance_descendant_ids() -> None:
    """Law: hydrated duplicates must not reuse another instance's scoped node ids."""
    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids
    from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances
    from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees

    template = CleanDesignTreeNode(
        id="4408:44897",
        name="Order product",
        type=NodeType.COLUMN,
        cluster_id="component_order_product",
        component_ref="1154:7859",
        children=[
            CleanDesignTreeNode(
                id="I4408:44897;1154:7849",
                name="Body",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id="I4408:44897;1154:7849;1149:9856;1149:9479;910:3261",
                        name="Minus",
                        type=NodeType.STACK,
                        children=[],
                    )
                ],
            )
        ],
    )
    duplicate = CleanDesignTreeNode(
        id="4408:44898",
        name="Order product",
        type=NodeType.COLUMN,
        cluster_id="component_order_product",
        component_ref="1154:7859",
        flatten_figma_node_ids=[
            "I4408:44897;1154:7849;1149:9856;1149:9479;910:3261",
        ],
        children=[],
    )
    root = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[template, duplicate],
    )
    prune_duplicated_cluster_subtrees(root)
    hydrate_pruned_cluster_instances(root)
    validate_unique_node_ids(root)
    hydrated = root.children[1]
    assert hydrated.children
    nested_id = hydrated.children[0].children[0].id
    assert nested_id.startswith("I4408:44898;")
    assert "44897" not in nested_id


def test_niyama_order_plan_hydrate_keeps_unique_node_ids() -> None:
    """Integration: niyama_order dump survives subtree prune + layout hydrate."""
    from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        activate_conservation_session,
    )
    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids
    from figma_flutter_agent.generator.layout.file import render_layout_file
    from figma_flutter_agent.generator.subtree import (
        collect_subtree_widget_specs,
        replace_extracted_subtree_nodes_with_refs,
    )
    from figma_flutter_agent.parser.boundaries.assets import (
        resolve_missing_image_asset_keys,
        resolve_pruned_cluster_instance_assets,
        resolve_render_boundary_asset_keys,
    )
    from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
    from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
    from figma_flutter_agent.stages import parse_figma_frame
    from figma_flutter_agent.stages.assets import finalize_screen_assets

    dump = Path("e:/@dev/figma-flutter-agent/.debug/screen/test/niyama_order/raw.json")
    project = Path("e:/@dev/figma-flutter-agent/apps/test")
    if not dump.is_file():
        return

    activate_conservation_session()
    fetch = load_fetch_result_from_dump(dump, file_key="dummy", node_id="4408:44885")
    parsed = parse_figma_frame(fetch)
    exclude = build_screen_frame_exclude_ids(fetch.node_id, set())
    manifest = local_asset_manifest_from_project(
        project,
        exclude_node_ids=exclude,
        clean_tree=parsed.clean_tree,
    )
    finalize_screen_assets(
        project_dir=project,
        clean_tree=parsed.clean_tree,
        destination_trees={},
        manifest=manifest,
        primary_node_id=fetch.node_id,
        destination_node_ids=set(),
    )
    resolve_render_boundary_asset_keys(parsed.clean_tree, project, manifest, strict=False)
    resolve_missing_image_asset_keys(parsed.clean_tree, project)
    resolve_pruned_cluster_instance_assets(parsed.clean_tree, project)

    subtree_specs = collect_subtree_widget_specs(
        parsed.clean_tree,
        widget_suffix="Widget",
    )
    replace_extracted_subtree_nodes_with_refs(parsed.clean_tree, subtree_specs)
    prune_generation_layout_tree(parsed.clean_tree, extracted_subtree_node_ids=frozenset())
    validate_unique_node_ids(parsed.clean_tree)

    tree = deepcopy(parsed.clean_tree)
    render_layout_file(tree, feature_name="niyama_order", uses_svg=True)
    validate_unique_node_ids(tree)
