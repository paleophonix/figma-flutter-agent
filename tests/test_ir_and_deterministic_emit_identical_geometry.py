"""G1 metric: deterministic and guarded IR paths share normalized geometry (T0.2)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.ir.context import IrEmitContext, IrEmitPolicy
from figma_flutter_agent.generator.ir.screen import emit_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import apply_ir_guards
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def _touch_target_screen() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="btn",
                name="CTA",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(
                    left=10.0,
                    top=10.0,
                    width=16.0,
                    height=16.0,
                ),
            ),
        ],
    )


def _extract_positioned_blocks(dart: str) -> list[str]:
    return re.findall(r"Positioned\([^)]*(?:\([^)]*\)[^)]*)*\)", dart, flags=re.DOTALL)


def _extract_sizedbox_44(dart: str) -> int:
    return len(re.findall(r"SizedBox\(width:\s*44(?:\.0)?,\s*height:\s*44", dart))


def test_normalize_and_ir_guards_yield_same_touch_target() -> None:
    root = _touch_target_screen()
    via_normalize = normalize_clean_tree(root)
    via_ir = apply_ir_guards(default_screen_ir(root), root)
    assert via_normalize.children[0].min_touch_target == via_ir.children[0].min_touch_target


def test_deterministic_and_ir_emit_share_touch_wrapping() -> None:
    root = _touch_target_screen()
    canonical = normalize_clean_tree(root)
    layout = render_layout_file(
        canonical,
        feature_name="g1_touch",
        uses_svg=False,
        skip_layout_reconcile=True,
    )["lib/generated/g1_touch_layout.dart"]
    screen_ir = default_screen_ir(canonical)
    ir_dart = emit_screen_code_from_ir(
        screen_ir,
        clean_tree=canonical,
        screen_class="G1TouchScreen",
        ctx=IrEmitContext(policy=IrEmitPolicy(apply_guards=False, validate=False)),
    )
    assert _extract_sizedbox_44(layout) >= 1
    assert _extract_sizedbox_44(ir_dart) >= 1
