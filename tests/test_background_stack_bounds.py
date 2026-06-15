"""Background header stack must be height-bounded inside Column scroll."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree

_DUMP = Path(r"e:\@dev\flutter-demo-project\demo_app\.debug\raw\background_layout.json")


def test_background_header_stack_has_single_height_bound() -> None:
    if not _DUMP.is_file():
        return
    raw = json.loads(_DUMP.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=_DUMP.parent.parent.parent,
    )
    layout = render_layout_file(
        root,
        feature_name="background",
        uses_svg=True,
        use_geometry_planner=True,
    )["lib/generated/background_layout.dart"]
    markers = ("figma-362_324", "figma-n_362_324")
    stack_idx = max(layout.find(marker) for marker in markers)
    assert stack_idx >= 0, "header blur node not found"
    prefix = layout[max(0, stack_idx - 220) : stack_idx]
    assert "height: 104.0" in prefix, prefix
    assert prefix.count("height: 104.0") == 1, prefix
    assert "child: Stack(" in prefix
