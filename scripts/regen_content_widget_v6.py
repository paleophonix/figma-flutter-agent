"""Regenerate demo ContentWidget from cached sign_up_version_6 IR + raw dump."""

import json
from pathlib import Path

from figma_flutter_agent.generator.ir.emitter import IrEmitContext, IrEmitPolicy, emit_merged_root_expression
from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir.tree import index_clean_tree, merge_screen_ir
from figma_flutter_agent.generator.layout.renderer import render_widget_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import ScreenIr

PROJECT = Path(r"E:/@dev/flutter-demo-project/demo_app")


def main() -> None:
    raw = json.loads(
        (PROJECT / ".figma_debug/raw/sign_up_version_6_layout.json").read_text(encoding="utf-8"),
    )
    tree, _, _, _ = build_clean_tree(raw)
    ir_payload = json.loads(
        (PROJECT / ".figma_debug/ir/sign_up_version_6_pre_emit.json").read_text(encoding="utf-8"),
    )
    screen_ir = ScreenIr.model_validate(ir_payload["screenIr"])
    norm = normalize_screen_ir_presence(screen_ir, tree)
    merged = merge_screen_ir(tree, norm)
    content = index_clean_tree(merged)["42:3215"]
    ctx = IrEmitContext(
        uses_svg=True,
        policy=IrEmitPolicy(validate=False, apply_guards=False),
        is_layout_root=True,
    )
    body = emit_merged_root_expression(content, ctx=ctx)
    out = render_widget_file(
        class_name="ContentWidget",
        body=body,
        uses_svg=True,
        source_file="lib/widgets/content_widget.dart",
    )
    target = PROJECT / "lib/widgets/content_widget.dart"
    target.write_text(out, encoding="utf-8")
    print(f"Wrote {target}")
    print(f"Register={'Register' in out} TextFields={out.count('TextField')}")


if __name__ == "__main__":
    main()
