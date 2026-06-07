# pipeline

## Purpose

Orchestrates Figma → Flutter generation: fetch, parse, optional LLM, plan, validate, write, incremental sync.

## Example

```python
from figma_flutter_agent.pipeline.run import run_pipeline

result = await run_pipeline(settings, figma_url=url, project_dir=path)
```

Submodules: `deps` (injectable factories), `helpers`, `llm`, `incremental`.

```python
from figma_flutter_agent.pipeline.deps import PipelineDependencies, default_pipeline_dependencies
from figma_flutter_agent.pipeline.run import run_pipeline

deps = default_pipeline_dependencies()
await run_pipeline(settings, figma_url=url, project_dir=path, deps=deps)
```

Override `deps.figma_connector`, `deps.create_llm_client`, or `deps.dart_writer_factory` in tests without patching imports.

## LLM Context

`run_pipeline` returns `PipelineResult` with `run_id` for log correlation. Production profile applies via CLI before calling.
