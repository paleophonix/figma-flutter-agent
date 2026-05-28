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
```

## LLM context

- Manifest: `tests/fixtures/screens.yaml`
- Layout JSON: `tests/fixtures/layouts/*.json` (clean design tree shape)
- `ac2: true` marks geometry stress fixtures (dirty layer names, not English copy)
