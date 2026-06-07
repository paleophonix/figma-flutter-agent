"""Geometry hardening TZ acceptance tests (WP-A/B/C/D)."""

from __future__ import annotations

import math

from figma_flutter_agent.generator.geometry.invariants import validate_geometry_invariants
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.generator.layout.widgets.render import _wrap_sizing
from figma_flutter_agent.parser.z_dag import ghost_occlusion_violations
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    LayoutSlotIr,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
    WrapKind,
)


def test_rotated_node_local_origin_placement() -> None:
    angle = math.radians(45.0)
    local = Affine2(
        a=math.cos(angle),
        b=math.sin(angle),
        c=-math.sin(angle),
        d=math.cos(angle),
        tx=12.0,
        ty=8.0,
    )
    node = CleanDesignTreeNode(
        id="rot",
        name="Rotated",
        type=NodeType.VECTOR,
        sizing=Sizing(width=40.0, height=40.0),
        geometry_frame=GeometryFrame(
            local_transform=local,
            intrinsic_size=GeomRect(width=40.0, height=40.0),
            layout_rect=GeomRect(x=12.0, y=8.0, width=40.0, height=40.0),
            placement_origin=GeomRect(x=12.0, y=8.0),
            parsed_world_aabb=GeomRect(x=12.0, y=8.0, width=56.0, height=56.0),
            world_aabb=GeomRect(x=12.0, y=8.0, width=56.0, height=56.0),
        ),
        stack_placement=StackPlacement(left=12.0, top=8.0, width=56.0, height=56.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=360.0, height=640.0),
        children=[node],
    )
    planned = plan_geometry_tree(root)
    slot = planned.children[0].layout_slot
    assert slot is not None
    pins = slot.positioned_pins
    assert pins is not None
    assert math.isclose(pins.left or 0.0, 12.0, abs_tol=0.5)
    assert math.isclose(pins.top or 0.0, 8.0, abs_tol=0.5)
    assert math.isclose(pins.width or 0.0, 40.0, abs_tol=0.5)


def test_no_double_flex_wrap() -> None:
    child = CleanDesignTreeNode(
        id="fill",
        name="Fill",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FILL, width=100.0, height=40.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.EXPANDED,)),
    )
    parent = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
    )
    wrapped = _wrap_sizing(
        child,
        "Container()",
        parent_type=NodeType.ROW,
        parent_node=parent,
    )
    assert wrapped.count("Expanded(") == 0


def test_ghost_detects_current_unsorted_order() -> None:
    decor = CleanDesignTreeNode(
        id="decor",
        name="Decor",
        type=NodeType.VECTOR,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=100.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=80.0, height=40.0),
        stack_placement=StackPlacement(left=10.0, top=10.0, width=80.0, height=40.0),
    )
    violations = ghost_occlusion_violations([button, decor])
    assert violations


def test_ast_coverage_fails_on_oversized_skip() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        layout_slot=LayoutSlotIr(),
    )
    violations = validate_geometry_invariants(root, sidecar_skipped=True)
    assert any(v.code == "inv_ast_coverage" for v in violations)


def test_cascade_context_wired_single_space() -> None:
    from figma_flutter_agent.generator.cascade_context import cascade_context_from_node

    angle = math.radians(30.0)
    local = Affine2(
        a=math.cos(angle),
        b=math.sin(angle),
        c=-math.sin(angle),
        d=math.cos(angle),
        tx=5.0,
        ty=7.0,
    )
    node = CleanDesignTreeNode(
        id="n",
        name="Node",
        type=NodeType.CONTAINER,
        geometry_frame=GeometryFrame(
            local_transform=local,
            intrinsic_size=GeomRect(width=20.0, height=10.0),
        ),
    )
    ctx = cascade_context_from_node(node)
    assert ctx is not None
    assert math.isclose(ctx.pivot_x, 5.0, abs_tol=1e-6)
    assert math.isclose(ctx.pivot_y, 7.0, abs_tol=1e-6)


def test_variant_topology_splits_divergent_subtree() -> None:
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

    left = CleanDesignTreeNode(
        id="v1",
        name="Primary",
        type=NodeType.BUTTON,
        cluster_id="cluster-a",
        children=[CleanDesignTreeNode(id="t1", name="Label", type=NodeType.TEXT)],
    )
    right = CleanDesignTreeNode(
        id="v2",
        name="Secondary",
        type=NodeType.BUTTON,
        cluster_id="cluster-a",
        children=[
            CleanDesignTreeNode(id="i1", name="Icon", type=NodeType.VECTOR),
            CleanDesignTreeNode(id="t2", name="Label", type=NodeType.TEXT),
        ],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        children=[left, right],
    )
    specs = collect_cluster_widget_specs(root, {"cluster-a": 2}, min_count=2)
    assert len(specs) == 2
