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
poetry run python scripts/generate_fixture_goldens.py --check
```

`load_layout_tree` applies the same root STACK paint ordering as `build_clean_tree`. Use `fixture-ir-validate --no-guards` for structure-only checks (no auto-mutations) before refreshing goldens.
```

## LLM context

- Manifest: `tests/fixtures/screens.yaml`
- Layout JSON: `tests/fixtures/layouts/*.json` (clean design tree shape)
- `ac2: true` marks geometry stress fixtures (dirty layer names, not English copy)
