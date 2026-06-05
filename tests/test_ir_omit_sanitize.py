"""Tests for screen IR omitFigmaIds sanitization."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence import (
    sanitize_screen_ir_omit_figma_ids,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir, merge_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_sanitize_omit_preserves_root_stack_children() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:art",
                name="Art",
                type=NodeType.STACK,
                stack_placement={
                    "left": 0.0,
                    "top": 0.0,
                    "width": 100.0,
                    "height": 100.0,
                },
            ),
            CleanDesignTreeNode(
                id="1:btn",
                name="SIGN UP",
                type=NodeType.TEXT,
                text="SIGN UP",
                stack_placement={
                    "left": 0.0,
                    "top": 50.0,
                    "width": 60.0,
                    "height": 14.0,
                },
            ),
        ],
    )
    screen_ir = default_screen_ir(root).model_copy(
        update={"omit_figma_ids": ["1:art", "1:btn", "1:noise"]},
    )
    sanitized = sanitize_screen_ir_omit_figma_ids(screen_ir, root)
    assert "1:art" not in sanitized.omit_figma_ids
    assert "1:btn" not in sanitized.omit_figma_ids
    assert "1:noise" in sanitized.omit_figma_ids
    merged = merge_screen_ir(root, sanitized)
    assert any(child.id == "1:art" for child in merged.children)
    assert any(child.id == "1:btn" for child in merged.children)


def test_sanitize_omit_preserves_sign_up_inside_button_stack() -> None:
    """LLM omit on label TEXT inside CONTAINER+TEXT stack (Group 6778) is ignored."""
    sign_up_label = CleanDesignTreeNode(
        id="1:3972",
        name="SIGN UP",
        type=NodeType.TEXT,
        text="SIGN UP",
        stack_placement={
            "left": 10.0,
            "top": 5.0,
            "width": 60.0,
            "height": 14.0,
        },
    )
    button_stack = CleanDesignTreeNode(
        id="1:3970",
        name="Group 6778",
        type=NodeType.STACK,
        stack_placement={
            "left": 0.0,
            "top": 200.0,
            "width": 120.0,
            "height": 40.0,
        },
        children=[
            CleanDesignTreeNode(
                id="1:3971",
                name="Rectangle",
                type=NodeType.CONTAINER,
                stack_placement={
                    "left": 0.0,
                    "top": 0.0,
                    "width": 120.0,
                    "height": 40.0,
                },
            ),
            sign_up_label,
        ],
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        children=[button_stack],
    )
    screen_ir = default_screen_ir(root).model_copy(
        update={"omit_figma_ids": ["1:3972"]},
    )
    sanitized = sanitize_screen_ir_omit_figma_ids(screen_ir, root)
    assert "1:3972" not in sanitized.omit_figma_ids
    merged = merge_screen_ir(root, sanitized)
    button_stack = next(c for c in merged.children if c.id == "1:3970")
    assert any(c.id == "1:3972" for c in button_stack.children)
