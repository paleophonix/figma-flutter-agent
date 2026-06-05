import json
from pathlib import Path

from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode

raw = json.loads(
    Path(r"e:\@dev\flutter-demo-project\demo_app\.figma_debug\raw\background_layout.json").read_text(
        encoding="utf-8"
    )
)
tree, _, _, _ = build_clean_tree(raw)
planned = plan_geometry_tree(tree)


def find(node: CleanDesignTreeNode, tid: str) -> CleanDesignTreeNode | None:
    if node.id == tid:
        return node
    for child in node.children:
        found = find(child, tid)
        if found is not None:
            return found
    return None


n = find(planned, "611:1330")
assert n is not None
slot = n.layout_slot
frame = n.geometry_frame
from figma_flutter_agent.generator.geometry.affine import expand_aabb

pins = slot.positioned_pins
residual = slot.residual_matrix or frame.local_transform
derived = expand_aabb(residual, frame.intrinsic_size.width, frame.intrinsic_size.height)
origin = frame.placement_origin
expected_x = pins.left + derived.x
expected_y = pins.top + derived.y
print("derived", derived)
print("expected", expected_x, expected_y)
print("origin", origin.x, origin.y)
print("err", abs(origin.x - expected_x), abs(origin.y - expected_y))
