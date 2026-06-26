# preview

## Purpose

Wizard and pipeline **preview** capture use the Flutter warm sandbox (`flutter test`) for chrome-parity PNGs. The optional `figma-flutter preview-capture --layout-json` CLI still uses a static HTML sketch renderer for offline fixtures only.

## Usage Example

```python
from pathlib import Path

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.preview import (
    PreviewCaptureRequest,
    capture_preview_png,
    preview_scene_from_clean_tree,
)

tree = load_layout_tree("consent_checkbox")
scene = preview_scene_from_clean_tree(tree)
result = capture_preview_png(
    PreviewCaptureRequest(
        scene=scene,
        output_path=Path(".debug/renders/preview.png"),
        screen_id="consent_checkbox",
    ),
)
assert result.ok
```

CLI:

```bash
poetry run figma-flutter preview-capture \
  --layout-json tests/fixtures/layouts/consent_checkbox_row.json \
  --out .debug/renders/preview.png
```

## LLM Context

`CaptureMode.PREVIEW` writes `<feature>_preview_capture.png` via browser preview (`capture_preview_png`; no Flutter test). `CaptureMode.ORACLE` uses warm-sandbox `flutter test` capture plus optional Figma diff heatmap.
