# Core modules (package root files)

Short reference for single-file modules under `src/figma_flutter_agent/`.

## errors.py

- **Purpose:** `FigmaFlutterError` hierarchy and `sanitize_api_message()` for API bodies.
- **Example:** `raise ParseError("node not visible")` on parse boundaries; `PipelineError` for internal invariant violations (CLI exit 2).
- **LLM context:** List expected types in public API `Raises` clauses.

## observability.py

- **Purpose:** `new_run_id()` and `log_stage()` context manager (`duration_ms`, stage name).
- **Example:** `with log_stage(log.bind(run_id=run_id), "fetch"): ...`
- **LLM context:** Bind `run_id`, `file_key`, `feature_name` on the logger before stages.

## pipeline_context.py

- **Purpose:** `PipelineContext` holds fetch/parse outputs and warnings between stages.
- **Example:** `ctx.apply_parse(parse_figma_frame(...))` then `ctx.require_parse_complete()`.
- **LLM context:** Pass `ctx.clean_tree` / `ctx.tokens` to planner after parse completes.

## schemas.py

- **Purpose:** Pydantic models shared by parser, LLM, and generator (`CleanDesignTreeNode`, `DesignTokens`, `FlutterGenerationResponse`).
- **Example:** `tree.model_dump(mode="json", by_alias=True)` for LLM user payload.
- **LLM context:** Use camelCase aliases in JSON (`vectorAssetKey`, `clusterId`).

## redaction.py

- **Purpose:** `redact_secrets()` for logs and error messages (Figma PAT, API keys, Bearer).
- **Example:** `sanitize_api_message(body)` in `FigmaApiError`.
- **LLM context:** Never log raw `.env` values; redaction runs before truncate in API errors.

## config.py

- **Purpose:** `Settings` (env + YAML), `apply_production_profile()`, agent nested config.
- **Example:** `settings = apply_production_profile(load_settings(path))`.
- **LLM context:** Production sets `require_strict_json_schema`, `strict_preservation`, `analyze_scope: all_planned`.
