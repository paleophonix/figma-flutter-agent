# fonts

## Purpose

Collect Figma `fontFamily` faces from any design tree, match files in `assets/fonts/` by **exact basename only** (e.g. `helvetica_neue_500.ttf` / `.otf`), then `*_analog.ttf` substitutes on disk, then registry/Google download (saved as `helvetica_neue_500_analog.ttf`), and merge `pubspec.yaml` `flutter.fonts` entries (never list `assets/fonts/` under `flutter.assets`). Analog usage always emits a warning.

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

Resolution order on run/fetch: exact original in `assets/fonts/` → exact `*_analog` on disk → registry substitute download → Google Fonts download (all substitutes use the `_analog` suffix). Weight profiles in the registry drive pubspec weights and Dart `FontWeight` overrides (for example bundled `w500` → `FontWeight.w700` for Helvetica Neue). Pass `frozenset(manifest.bundled_family_names)` into layout codegen so bundled families omit `fontFamilyFallback`. `manifest.family_aliases` maps raw Figma names to pubspec family names.
