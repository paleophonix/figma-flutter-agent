"""Tests for LAW-RESPONSIVE-DEFN layout tier classification."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.checks.layout import (
    build_responsiveness_report,
    classify_clean_tree_responsive_tier,
    classify_layout_responsive_tier,
    validate_responsive_reflow_required,
)
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.layout.widgets.positioned import _stack_has_bottom_anchored_child
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_classify_preview_tier_when_artboard_defines_present() -> None:
    source = """
    if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0) {
      return ClipRect(child: SizedBox(width: _artboardPreviewWidth, child: child));
    }
    return SizedBox(width: 375.0, child: Stack(children: []));
    """
    assert classify_layout_responsive_tier(source) == "preview"


def test_classify_scaled_tier_for_root_fitted_box() -> None:
    source = """
    return LayoutBuilder(builder: (context, constraints) {
      return Align(
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: SizedBox(width: 375.0, height: 812.0, child: Stack(children: [])),
        ),
      );
    });
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.STACK) == "scaled"


def test_classify_reflowed_tier_for_scroll_column_without_scale() -> None:
    source = """
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [Text('hello')],
      ),
    );
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.COLUMN) == "reflowed"


def test_classify_reflowed_when_preview_branch_has_fitted_box_only() -> None:
    source = """
    if (_artboardPreviewWidth > 0) {
      return FittedBox(fit: BoxFit.scaleDown, child: SizedBox(width: 375.0, child: body));
    }
    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [body]),
    );
    """
    assert classify_layout_responsive_tier(source, root_type=NodeType.COLUMN) == "reflowed"


def test_require_reflow_gate_blocks_scaled_layout() -> None:
    scaled = """
    return LayoutBuilder(builder: (context, constraints) {
      return FittedBox(
        fit: BoxFit.scaleDown,
        child: SizedBox(width: 375.0, height: 812.0, child: Stack(children: [])),
      );
    });
    """
    try:
        validate_responsive_reflow_required(
            {"lib/generated/demo_layout.dart": scaled},
            [],
            require_reflow=True,
            responsive_enabled=True,
        )
        raised = False
    except GenerationError:
        raised = True
    assert raised is True


def test_stack_has_bottom_anchored_child_by_geometry_top_pin() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=375.0,
            height=903.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="panel",
                name="Panel",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=184.0),
                stack_placement=StackPlacement(
                    left=0.0,
                    top=719.0,
                    width=375.0,
                    height=184.0,
                ),
            ),
        ],
    )
    assert _stack_has_bottom_anchored_child(root) is True


def test_root_stack_with_bottom_panel_emits_scroll_not_fitted_box() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=375.0,
            height=903.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=375.0, height=903.0),
        ),
        children=[
            CleanDesignTreeNode(
                id="hero",
                name="Hero",
                type=NodeType.TEXT,
                text="Hero",
                sizing=Sizing(width=327.0, height=184.0),
                stack_placement=StackPlacement(left=24.0, top=139.0, width=327.0, height=184.0),
            ),
            CleanDesignTreeNode(
                id="panel",
                name="Panel",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=184.0),
                stack_placement=StackPlacement(
                    left=0.0,
                    top=719.0,
                    width=375.0,
                    height=184.0,
                ),
            ),
        ],
    )
    body = render_node_body(
        root,
        uses_svg=False,
        is_layout_root=True,
        responsive_enabled=True,
    )
    assert "FittedBox(fit: BoxFit.scaleDown" not in body


def test_classify_clean_tree_reflowed_after_sectionize() -> None:
    payload = json.loads(
        Path("tests/fixtures/layouts/product_detail_vertical.json").read_text(encoding="utf-8"),
    )
    clean = CleanDesignTreeNode.model_validate(payload)
    screen_ir = default_screen_ir(clean)
    _, updated = apply_ir_layout_passes(screen_ir, clean, validate_cp2=False)
    assert classify_clean_tree_responsive_tier(updated) == "reflowed"
    report = build_responsiveness_report(updated)
    assert report["verdict"] == "pass"
    assert report["tier"] == "reflowed"
