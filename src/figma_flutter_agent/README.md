# figma_flutter_agent

Python package: Figma frame → Material 3 Flutter codegen (CLI `figma-flutter`).

## Module map

| Path | Role |
|------|------|
| `cli.py` | Typer commands: `generate`, `demo-signoff`, `live-check`, `validate-spec23` |
| `pipeline/` | Orchestrates stages; `deps.py` composition root (`PipelineDependencies`) |
| `pipeline_context.py` | Mutable fetch/parse state for `run_pipeline` |
| `config.py` | `Settings`, YAML merge, `apply_production_profile()` |
| `figma/` | REST connector (retry, batching) |
| `parser/` | Clean tree, tokens, CSS synthesis (REST), accessibility |
| `generator/` | Planner, Jinja templates, deterministic layout, writer + preservation |
| `stages/` | `fetch`, `parse`, `llm`, `validate`, `write` |
| `sync/` | File-hash incremental sync, snapshot |
| `llm/` | Structured-output clients (Anthropic, OpenAI, OpenRouter, Google) |
| `validation/` | Spec §23 evaluator |
| `observability.py` | `new_run_id()`, stage timing (`log_stage`, `duration_ms`, failed vs completed) |
| `errors.py` | `FigmaFlutterError` hierarchy, `sanitize_api_message` |
| `redaction.py` | Shared secret redaction for logs and API errors |
| `schemas.py` | Pydantic models: clean tree, tokens, LLM `FlutterGenerationResponse` |

## Quickstart

```bash
poetry install --with dev
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter generate --figma-url "FIGMA_URL" --project-dir ../demo_app
```

Dev-only (no production gates): add `--allow-dev-profile`.

## LLM context

- Config: agent repo `.ai-figma-flutter.yml` + `.env` (`FIGMA_ACCESS_TOKEN`, `LLM_PROVIDER`, `LLM_GENERATE_MODEL`, optional repair/refine models, keys)
- Preservation: edit only `// <custom-code>` blocks in generated Dart
- Spec deltas & limits: repo [README.md](../../README.md#spec-interpretation)
- IDE: [README.md](../../README.md#vs-code--cursor), [AGENTS.md](../../AGENTS.md)
