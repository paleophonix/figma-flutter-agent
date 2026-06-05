import json
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
lines = [f"Flexible count: {src.count('Flexible(fit')}"]
idx = 0
for n in range(10):
    j = src.find("Flexible(fit", idx)
    if j < 0:
        break
    lines.append(f"--- hit {n} @ {j} ---")
    lines.append(src[j - 150 : j + 220])
    idx = j + 1
Path(r"e:\@dev\figma-flutter-agent\flex_ctx.txt").write_text("\n".join(lines), encoding="utf-8")
