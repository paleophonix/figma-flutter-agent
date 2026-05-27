# fonts

## Purpose

Optional visual QA helpers: export Figma reference PNGs, emit Flutter golden test scaffolds, and compare pixels offline.

## Example

```python
from figma_flutter_agent.validation.compare import run_visual_qa

report = run_visual_qa(project_dir, "sign_in", threshold=0.05)
assert report.passed
```

```bash
# After flutter test --update-goldens in the Flutter project:
poetry run figma-flutter visual-qa compare --project-dir ../demo_app --feature sign_in
```

## LLM context

Table E typography specimens live in `data/font-specimens.v1.yaml` (10 blocks). When `validation.generate_typography_specimen_test: true`, emits `test/golden/typography_specimens_test.dart` with per-specimen golden files `test/goldens/spec_*.png`. Full-screen diff compares `.figma-flutter/reference/{feature}_figma.png` vs `test/goldens/{feature}_screen.png` using Pillow (5% changed-pixel default). Specimen Figma references are optional at `.figma-flutter/reference/specimens/{id}.png`.
