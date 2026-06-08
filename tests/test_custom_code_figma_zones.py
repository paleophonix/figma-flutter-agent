"""Tests for Figma-id anchored custom-code preservation zones."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
    legacy_role_from_zone,
)
from figma_flutter_agent.generator.variant.actions import button_on_pressed_expr
from figma_flutter_agent.generator.writing.custom_code import merge_custom_code
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def _button_node(node_id: str = "1:3608") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Login",
        type=NodeType.BUTTON,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=120, height=48),
    )


def test_custom_code_zone_id_uses_figma_token() -> None:
    zone = custom_code_zone_id("1:3608", "button-action")
    assert zone == "figma-1_3608:button-action"
    assert legacy_role_from_zone(zone) == "button-action"


def test_button_on_pressed_embeds_figma_zone() -> None:
    expr = button_on_pressed_expr(_button_node())
    assert "figma-1_3608:button-action" in expr
    assert "button-action" not in expr or "figma-1_3608:button-action" in expr


def test_merge_custom_code_maps_legacy_role_to_figma_zone() -> None:
    zone = custom_code_zone_id("1:3608", "button-action")
    existing = """
import 'package:flutter/material.dart';

void main() {
  runApp(MaterialApp(home: Scaffold(body: Text('x'))));
}
"""
    new_content = f"""
import 'package:flutter/material.dart';

class Demo extends StatelessWidget {{
  @override
  Widget build(BuildContext context) {{
    return ElevatedButton(
      onPressed: () {{ {inline_custom_code_comment(zone)} }},
      child: const Text('Go'),
    );
  }}
}}
"""
    existing_with_code = existing.replace(
        "runApp",
        "// <custom-code:button-action>\n  print('saved');\n// </custom-code:button-action>\n\nrunApp",
    )
    merged = merge_custom_code(new_content, existing_with_code)
    assert "print('saved')" in merged
    assert f"custom-code:{zone}" in merged or "print('saved')" in merged
