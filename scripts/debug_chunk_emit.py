"""Debug helper: render profile_partner chunk after normalize (like planner)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.stages.assets import apply_asset_manifest


def main() -> None:
    project = Path(r"e:/@dev/flutter-demo-project/ataev")
    raw = json.loads(
        (project / ".figma_debug/raw/profile_partner_layout.json").read_text(
            encoding="utf-8"
        )
    )
    tree, *_ = build_clean_tree(raw)
    manifest = local_asset_manifest_from_project(project)
    apply_asset_manifest(tree, manifest)
    tree = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=True,
        project_dir=project,
    )
    planned = render_layout_file(
        tree,
        feature_name="profile_partner",
        uses_svg=True,
        package_name="ataev",
        use_geometry_planner=True,
    )
    chunk = planned.get("lib/generated/profile_partner_chunk_e5c64fa5.dart", "")
    out = Path("tmp_chunk_debug.txt")
    lines = [f"chunk_bytes={len(chunk)}"]
    for match in re.finditer(r"SvgPicture\.asset\([^)]+\)", chunk):
        lines.append(match.group()[:150])
    out.write_text("\n".join(lines), encoding="utf-8")
    out.with_suffix(".dart").write_text(chunk, encoding="utf-8")


if __name__ == "__main__":
    main()
