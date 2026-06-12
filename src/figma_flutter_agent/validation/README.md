# validation

Pixel diff, golden capture, and spec gates.

## Example

```python
from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png

result = capture_planned_flutter_golden_png(planned, feature_name="auth", settings=settings)
```

`runtime.golden_capture: auto` prefers Docker when `docker compose` and `tools/render-capture` exist.

## LLM context

Golden PNG bytes feed visual refine; use `FIGMA_GOLDEN_RUNTIME=host` locally without Docker.

`pixeldiff.compare_png_files_with_text_mask` runs stage-1 TEXT coordinate validation
(``text_coordinate_tolerance``, default 3px) then black-box masks TEXT regions before
pixel diff (``llm_visual_refine_threshold``, default 0.5%). Golden capture writes
``test/goldens/{feature}_figma_keys.json`` for runtime bounds.

Combat-mode captures during `figma-flutter generate` are written under `<project>/.debug/renders/{timestamp}-{run_id}/`
(`figma_reference`, `flutter_render.png` / `flutter_render_*`, `diff_heatmap_*`, `manifest.jsonl`). CLI prints the folder path on success. The Flutter PNG appears only after `flutter test --update-goldens` finishes (often 1–5 min after refine starts).
