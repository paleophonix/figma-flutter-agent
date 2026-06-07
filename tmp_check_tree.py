import json
from pathlib import Path

from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree

raw = json.loads(
    Path(r"e:/@dev/flutter-demo-project/ataev/.figma_debug/raw/profile_edit_layout.json").read_text(
        encoding="utf-8"
    )
)
tree, _, _, _ = build_clean_tree(raw)
root = normalize_clean_tree(tree, use_geometry_planner=True, apply_render_safety=False)


def find(node, nid: str):
    if node.id == nid:
        return node
    for child in node.children:
        found = find(child, nid)
        if found is not None:
            return found
    return None


for nid in ("362:332", "611:1330"):
    node = find(root, nid)
    assert node is not None
    print(nid, "type", node.type, "effects", node.style.effects)
    print("  expand", node.style.render_bounds_expand)
