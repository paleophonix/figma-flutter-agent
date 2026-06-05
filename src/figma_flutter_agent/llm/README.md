# llm

## Purpose

Structured Flutter codegen via provider-specific LLM clients (Anthropic, OpenAI, OpenRouter, Google AI Studio / Gemini). Set `LLM_PROVIDER=google` or `google_aistudio` with `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey). Provider capabilities live in `capabilities.py`.

## Example

```python
from figma_flutter_agent.llm.client import create_llm_client

llm = create_llm_client(provider="anthropic", api_key=key, model="claude-sonnet-4-6")
response = await llm.generate_async(
    clean_tree,
    tokens,
    feature_name="onboarding",
    asset_manifest=[],
    figma_reference_png=optional_png_bytes,
)
```

OpenRouter/Google use `json_schema` with `strict: false` and log `structured_output_fallback` on each call. Production profile requires `anthropic` or `openai` with `require_strict_json_schema: true`.

```python
# sync helper (tests/CLI); pipeline uses generate_async
response = llm.generate(clean_tree, tokens, feature_name="onboarding", asset_manifest=[])
```

## LLM Context

Output must validate as `FlutterGenerationResponse` (`screenCode` or `screenIr`, plus `extractedWidgets`). When `generation.use_screen_ir: true` (LLM path only), the model emits `screenIr` and `extractedWidgets[].widgetIr` (no Dart); the planner materializes via `generator/ir/emitter.py` (`screenIrBlueprint` / `extractedWidgetBlueprints` in the user payload). Visual refine and repair follow the same IR contract; unified-diff `patches` on planned Dart clear `screenIr` / `widgetIr` on the touched targets. System prompts in `prompts.py` are composed via `_compose_acdp_prompt` with strict **L1→L6** order; recurring LLM defects are listed in `SYSTEMIC_BUG_RULES` (injected as `_L3_SYSTEMIC_BUG_REGISTRY` into generate/repair/refine) — extend that tuple when fixing a new pipeline-wide bug (see `.cursor/rules/universal-codegen.mdc`); conditional blocks inject into **`l3_principles_ext`** / **`l5_actions_ext`** placeholders (never after L6). Figma matrices live in the **user message** as labeled `###` sections (`payload_format.format_labeled_user_payload`). `payload_slim.py` prunes null/false/empty fields, drops default strings (`none`, `AUTO`), clears duplicate `clusterId` subtrees on LLM export, drops redundant `offsetX`/`offsetY` when `stackPlacement` is present, and prunes flat token maps before serialization. No `<Thinking>` tags — only API structured JSON.

When `generation.llm_figma_reference_image: true` (default), the pipeline fetches a Figma PNG export at `validation.reference_scale` and attaches it to the LLM user message. The system prompt adds `<L3:PRINCIPLES_VISUAL_GOLD>`: the screenshot is the authoritative reference for layout, spacing, typography, and hierarchy. Offline `--from-dump` runs load `.figma-flutter/reference/{feature}_figma.png` when present.

Repair uses `_REPAIR_APR` with `Template.safe_substitute` for L6 analyzer context. **`llm_repair_prompt_escalation`** (default true): each attempt 1→`llm_repair_max_attempts` (default 4) gets a different **system** prompt via `RepairPromptEscalator` — level 1 standard APR, levels 2–4 metacognitive supervisor frame with escalating tactical directives; `build_repair_scope(..., escalation_level≥2)` widens targets to all `lib/widgets/` paths. When analyze errors repeat (`llm_repair_cpi_supervisor`, default true), `run_analyze_repair_loop` also calls `cpi_supervisor_async` and injects `patternInterruptDirective` into the next repair pass via `<L6:ENVIRONMENT>` (orthogonal to per-attempt escalation).

Reasoning is configured via `LLM_REASONING_EFFORT`, `LLM_REASONING_MAX_TOKENS`, and `LLM_REASONING_EXCLUDE` in `.env`. Strict JSON schema via `LLM_REQUIRE_STRICT_JSON_SCHEMA`. Pipeline LLM usage (repair/refine loops, fallback) is in agent-repo `.ai-figma-flutter.yml` under `generation:`.

Visual refine passes structured context in labeled user sections: `interactiveInventory`, `handlerAudit`, `visualDiff`, `refineFocus`, `canvasSize`, `assetWarnings`, `attachedImages`, optional `refineHistory`. Each attached PNG has an inline label immediately before its block. Helpers live in `refine_context.py`.
