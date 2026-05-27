# fonts

## Purpose

Collect Figma `fontFamily` faces from any design tree, auto-download matching font files (Google Fonts + proprietary substitutes), write `assets/fonts/`, and merge `pubspec.yaml` font entries.

Substitution rules live in `data/font-registry.v1.yaml` (normalization, weight profiles, ~92 family mappings). Regenerate the YAML with `poetry run python scripts/generate-font-registry.py`.

Per-project tuning: add `project-font-overrides.json` at the Flutter project root to override registry families or patch weight profiles. Downloaded font binaries are cached under `~/.config/figma-flutter-agent/cache/fonts` (override with `FIGMA_FLUTTER_FONT_CACHE_DIR`).

## Example

```python
from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.fonts.apply import apply_font_manifest

manifest = bundle_fonts_for_tree(clean_tree, project_dir)
apply_font_manifest(clean_tree, manifest)
```

## LLM context

Resolution order: registry bundled packages (for example Helvetica Neue via Inter + TeX Gyre italics) → registry Google slug (`gwfh`) → universal Noto Sans fallback. Weight profiles in the registry drive pubspec weights and Dart `FontWeight` overrides (for example bundled `w500` → `FontWeight.w700` for Helvetica Neue). Pass `frozenset(manifest.bundled_family_names)` into layout codegen so bundled families omit `fontFamilyFallback`. `manifest.family_aliases` maps raw Figma names to pubspec family names.
