"""Diagnose INPUT 362:356 emit from processed background tree."""
from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.layout.widget import render_node_body
from figma_flutter_agent.parser.interaction import (
    _is_input_decorative_control,
    _local_nodes,
    _stack_has_vector_icon,
    input_children_are_presentational,
    input_trailing_chrome_nodes,
    looks_like_input_trailing_icon_button,
)
from figma_flutter_agent.parser.interaction import _MAX_LOCAL_DEPTH
from figma_flutter_agent.schemas import CleanDesignTreeNode

PROCESSED = Path(
    r"e:\@dev\flutter-demo-project\demo_app\.figma_debug\processed\background_layout.json"
)


def _walk_buttons(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    out: list[CleanDesignTreeNode] = []
    if node.type.value == "BUTTON":
        out.append(node)
    for child in node.children:
        out.extend(_walk_buttons(child))
    return out


def find(node: CleanDesignTreeNode, nid: str) -> CleanDesignTreeNode | None:
    if node.id == nid:
        return node
    for child in node.children:
        found = find(child, nid)
        if found is not None:
            return found
    return None


def main() -> None:
    data = json.loads(PROCESSED.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(data["cleanTree"])
    for nid in ("362:356", "362:354", "362:327"):
        node = find(root, nid)
        if node is None:
            print(f"{nid}: NOT FOUND")
            continue
        print(f"\n=== {nid} type={node.type} ===")
        if node.type.value == "INPUT":
            print("presentational:", input_children_are_presentational(node))
            print("trailing:", [t.id for t in input_trailing_chrome_nodes(node)])
            for c in _walk_buttons(node):
                locals_ = _local_nodes(c, _MAX_LOCAL_DEPTH)
                print(
                    f"  BUTTON {c.id} size={c.sizing.width}x{c.sizing.height} "
                    f"trailing_icon={looks_like_input_trailing_icon_button(c)} "
                    f"decorative={_is_input_decorative_control(c)} "
                    f"has_vector={_stack_has_vector_icon(locals_)} "
                    f"local_types={[n.type.value for n in locals_]}"
                )
        body = render_node_body(
            node,
            uses_svg=False,
            responsive_enabled=True,
            design_artboard_width=390.0,
        )
        print("TextField:", "TextField" in body)
        print("F6F6F2:", "0xFFF6F6F2" in body)
        print("calendar:", "calendar" in body)
        print("snippet:", body[:400])


if __name__ == "__main__":
    main()
