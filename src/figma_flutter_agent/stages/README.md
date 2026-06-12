# stages

## Purpose

Decomposed pipeline stages: fetch, parse, assets, LLM, plan, validate, write, and snapshot.

## Example

```python
from figma_flutter_agent.stages import (
    fetch_figma_frame,
    parse_figma_frame,
    plan_generation_output,
    run_llm_stage,
    validate_planned_generation,
)
```

## LLM Context

Each stage returns a typed dataclass (`FigmaFetchResult`, `FigmaParseResult`, `LlmStageResult`, etc.) that the orchestrator in `pipeline.py` composes into `GenerationPlanContext` before write/snapshot.

### Fetch stage (`fetch.py`)

Parallel REST calls: nodes, variables, styles, components, component sets. Resolves prototype overlay destinations and published style paint nodes with follow-up `fetch_nodes`. The pipeline writes raw dumps to `project_dir/.debug/raw/<feature>_layout.json` and processed trees to `.debug/processed/<feature>_layout.json` after parse.

```bash
figma-flutter live-check --dump
```
