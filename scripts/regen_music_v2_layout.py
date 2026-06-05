"""Regenerate demo_app music_v2_layout.dart from processed dump."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode

PROJECT = Path(r"E:/@dev/flutter-demo-project/demo_app")


def main() -> None:
    dump = PROJECT / ".figma_debug/processed/music_v2_layout.json"
    tree = CleanDesignTreeNode.model_validate(
        json.loads(dump.read_text(encoding="utf-8"))["cleanTree"],
    )
    files = render_layout_file(
        tree,
        feature_name="music_v2",
        uses_svg=True,
        responsive_enabled=True,
    )
    target = PROJECT / "lib/generated/music_v2_layout.dart"
    target.write_text(files["lib/generated/music_v2_layout.dart"], encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
