# llm

## Purpose

Structured Flutter codegen via provider-specific LLM clients (Anthropic, OpenAI, OpenRouter, Google Gemini). Provider capabilities and strict-schema requirements live in `capabilities.py`.

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

Output must validate as `FlutterGenerationResponse` (`screenCode`, `extractedWidgets`). Prompt payload uses camelCase aliases for tree/tokens JSON. System prompts list clean-tree semantic types (GRID, TABS, CAROUSEL, form controls) and variant property mapping for LLM parity with the deterministic renderer.

When `generation.llm_figma_reference_image: true` (default), the pipeline fetches a Figma PNG export at `validation.reference_scale` and attaches it to the LLM user message. The system prompt adds a **VISUAL GOLD STANDARD** block: the screenshot is the authoritative reference for layout, spacing, typography, and hierarchy. Offline `--from-dump` runs load `.figma-flutter/reference/{feature}_figma.png` when present.

Reasoning is configured via `LLM_REASONING_EFFORT`, `LLM_REASONING_MAX_TOKENS`, and `LLM_REASONING_EXCLUDE` in `.env`. Strict JSON schema via `LLM_REQUIRE_STRICT_JSON_SCHEMA`. Pipeline LLM usage (repair/refine loops, fallback) is in agent-repo `.ai-figma-flutter.yml` under `generation:`.

Visual refine passes structured context in the user JSON: `interactiveInventory`, `handlerAudit`, `visualDiff.diffRegions`, `refineFocus` (one area per attempt), `canvasSize`, `assetWarnings`, and `attachedImages` (figma_reference vs flutter_render roles). Each attached PNG has an inline label immediately before its block. Helpers live in `refine_context.py`.
