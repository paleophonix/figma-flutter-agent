# OpenCode context assets

## Purpose

Curated navigation data injected into repair pipeline L6 templates. Not sent as full files to every step — orchestrator slices by step, board, and selected paths.

## Layout

```text
context/
  repo-map.yaml           # module atlas: global, screenSymptomHints, forensicSurfaces, deepModules
  law-label-map-ru.yaml   # lawId → RU label for summarize ticket prose
  README.md
```

## Usage example (planned)

```python
from figma_flutter_agent.dev.opencode.repo_map import slice_repo_map_for_step

payload = slice_repo_map_for_step(
    step="inspect",
    board="screen",
    symptom_ids=["text_duplication_and_overlap_in_form"],
)
# → inject as repo_map_compact_json in l6-environment.tpl
```

## LLM context

Repo map is **navigation only**, not evidence. Inspect uses global + symptomHints. Diagnose/plan/repair get lazy `deepModules` for selected repo paths. Fix step must not receive repo map.

Law label map is **translation only** for summarize ticket RU prose. Summarize step injects `law_label_map_ru_json`; unknown laws fall back to short plain RU from review/diagnose.
