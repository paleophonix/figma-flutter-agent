import json
import re
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree

raw = json.loads(
    Path(r"e:\@dev\flutter-demo-project\demo_app\.figma_debug\raw\background_layout.json").read_text(
        encoding="utf-8"
    )
)
tree, _, _, _ = build_clean_tree(raw)
root = normalize_clean_tree(
    tree,
    use_geometry_planner=True,
    apply_render_safety=False,
    project_dir=Path(r"e:\@dev\flutter-demo-project\demo_app"),
)
src = render_layout_file(root, feature_name="background", uses_svg=True)[
    "lib/generated/background_layout.dart"
]
patterns = [
    r"Padding\([^)]*child:\s*Flexible",
    r"Padding\(padding:[^)]*child:\s*Flexible",
    r"DecoratedBox\([^)]*child:\s*Flexible",
]
out = []
for pat in patterns:
    for m in re.finditer(pat, src):
        out.append(src[max(0, m.start() - 60) : m.start() + 220])
Path(r"e:\@dev\figma-flutter-agent\scan2.txt").write_text("\n\n---\n\n".join(out) or "none", encoding="utf-8")
