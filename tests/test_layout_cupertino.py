"""Cupertino deterministic layout tests."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import NodeType


def test_cupertino_layout_uses_cupertino_button() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(
        tree,
        feature_name="onboarding",
        uses_svg=False,
        theme_variant="cupertino",
    )["lib/generated/onboarding_layout.dart"]

    assert "import 'package:flutter/cupertino.dart';" in layout
    if tree.type == NodeType.STACK:
        assert "CupertinoPageScaffold" in layout
    assert "InkWell(" not in layout
