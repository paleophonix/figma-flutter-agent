# fixtures

Canonical offline screen layouts for golden and geometry tests.

## Example

```python
from figma_flutter_agent.fixtures import load_layout_tree, load_screens_manifest
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files

manifest = load_screens_manifest()
tree = load_layout_tree("music_v2_ru_dirty")
planned = build_fixture_planned_files("music_v2")
```

Golden PNG baselines:

```bash
poetry run python scripts/generate_fixture_goldens.py --golden-runtime docker

Bulk IR guardrails (all manifest screens):

```bash
poetry run python scripts/run_fixture_ir_validate.py
poetry run figma-flutter fixture-ir-validate
poetry run figma-flutter fixture-golden-check --threshold 0.05
poetry run figma-flutter fixture-geometry-check
# CI uses FIGMA_GEOMETRY_SIGNOFF_SCREENS=sign_up_and_sign_in for a single screen
poetry run python scripts/generate_fixture_goldens.py --check
```

`load_layout_tree` applies the same root STACK paint ordering as `build_clean_tree`. Use `fixture-ir-validate --no-guards` for structure-only checks (no auto-mutations) before refreshing goldens.

Corpus oracle (EPIC 6 W0):

```bash
poetry run figma-flutter corpus-oracle gate --blocking --write-report-dir logs/oracle
```

Manifest field `corpus_tier`: `strict_pixel_blocking` | `advisory_pixel` | `semantic_only`.
Blocking gates use `non_text_pixel_diff` and `geometry_iou`; `text_region_pixel_diff` is advisory until E7.
```

## LLM context

- Manifest: `tests/fixtures/screens.yaml`
- Layout JSON: `tests/fixtures/layouts/*.json` (clean design tree shape)
- `ac2: true` marks geometry stress fixtures (dirty layer names, not English copy)
