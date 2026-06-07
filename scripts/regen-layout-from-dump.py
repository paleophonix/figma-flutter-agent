"""Regenerate *_layout.dart from a cached .figma_debug raw layout dump (no Figma API)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from figma_flutter_agent.debug.dart_bundle import write_dart_debug_bundle
from figma_flutter_agent.fonts.apply import apply_font_manifest
from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import AssetManifest, AssetManifestEntry
from figma_flutter_agent.stages.assets import apply_asset_manifest


def _node_id_from_icon_filename(stem: str) -> str | None:
    match = re.search(r"(\d+)_(\d+)$", stem)
    if not match:
        return None
    return f"{match.group(1)}:{match.group(2)}"


def _manifest_from_project(project_dir: Path) -> AssetManifest:
    entries: list[AssetManifestEntry] = []
    icons_dir = project_dir / "assets" / "icons"
    if icons_dir.is_dir():
        for path in icons_dir.glob("*.svg"):
            node_id = _node_id_from_icon_filename(path.stem)
            if node_id is None:
                continue
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/icons/{path.name}",
                    kind="icon",
                )
            )
    return AssetManifest(entries=entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True, help="Path to .figma_debug/raw/<feature>_layout.json")
    parser.add_argument("--project-dir", type=Path, required=True, help="Flutter project root")
    parser.add_argument("--feature", default="sign_in", help="Feature folder name")
    parser.add_argument("--package-name", default="demo_app", help="pubspec name")
    parser.add_argument("--skip-fonts", action="store_true", help="Skip font bundling")
    args = parser.parse_args()

    root = json.loads(args.dump.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    apply_asset_manifest(tree, _manifest_from_project(args.project_dir))
    font_manifest = bundle_fonts_for_tree(
        tree,
        args.project_dir,
        enabled=not args.skip_fonts,
    )
    apply_font_manifest(tree, font_manifest)
    planned = render_layout_file(
        tree,
        feature_name=args.feature,
        uses_svg=True,
        package_name=args.package_name,
        bundled_font_families=frozenset(font_manifest.bundled_family_names),
        dart_weight_overrides_by_family=font_manifest.dart_weight_overrides_by_family,
    )
    gen_dir = args.project_dir / "lib" / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    wrote: list[Path] = []
    for rel, content in sorted(planned.items()):
        if not rel.startswith("lib/generated/"):
            continue
        out = args.project_dir / rel
        out.write_text(content, encoding="utf-8")
        wrote.append(out)
    for out in wrote:
        print(f"Wrote {out}")

    bundle_planned = dict(planned)
    screen_rel = f"lib/features/{args.feature}/{args.feature}_screen.dart"
    screen_path = args.project_dir / screen_rel
    if screen_path.is_file():
        bundle_planned[screen_rel] = screen_path.read_text(encoding="utf-8")
    bundle_path = write_dart_debug_bundle(
        args.project_dir,
        feature_name=args.feature,
        planned_files=bundle_planned,
        package_name=args.package_name,
    )
    if bundle_path is not None:
        print(f"Updated debug bundle {bundle_path}")

    if font_manifest.families:
        batch = update_pubspec(args.project_dir, ["assets/fonts/"], font_manifest=font_manifest)
        commit_pubspec_batch(batch)
        print(f"Updated pubspec fonts ({len(font_manifest.families)} families)")
    for warning in font_manifest.warnings:
        print(f"Font warning: {warning}")


if __name__ == "__main__":
    main()
