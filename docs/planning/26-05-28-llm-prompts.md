# LLM prompts — supervisor handbook

Canonical code: `src/figma_flutter_agent/llm/prompts.py`, context assembly: `llm/repair_scope.py`, user JSON: `llm/repair.py`, wiring: `llm/client.py`.

## Pipeline modes

| Mode | System builder | User payload | Theme M3 / Cupertino |
|------|----------------|--------------|----------------------|
| **generate** | `build_system_prompt()` | `_build_user_prompt` → JSON with `cleanTree`, tokens, hints | Yes |
| **repair** | `build_repair_system_prompt(context)` | `build_repair_user_payload()` | No (APR only) |
| **visual refine** | `build_visual_refine_system_prompt()` | `build_visual_refine_user_payload()` | Yes (via generate base) |

Default screen path is **deterministic** (`use_deterministic_screen: true`); LLM generate prompts apply when that flag is off.

## Placeholder contract (backend standard)

| Mode | System prompt | User payload |
|------|---------------|--------------|
| **generate** / **refine** | Static invariants only (`prompts.py`) | All data: `cleanTree`, tokens, hints, images via `client.py` JSON |
| **repair** | `string.Template` + `$placeholders` + `safe_substitute` | `build_repair_user_payload()` JSON |

Repair L6 fields: `$analyzeErrors` (bullet list), `$code` (`001| ` lines), `$semanticHint` (JSON or `null`), `$failedAttemptsHistory` (JSON array of strings), `$unchangedWidgetNames` (JSON array).

No `<Thinking>` tags in generate/repair output — conflicts with strict structured JSON schema.

## Generate — assembly

```
_THEME_* = role + _JSON_SCHEMA_GRAMMAR + theme-specific rules + _SHARED_LAYOUT_RULES
_GENERATE[theme] = _THEME_* + _INTERACTIVE_RULES + _ROUTING_OFF
build_system_prompt()
  + _APPEND_ROUTING          if routing_enabled
  + _APPEND_FIGMA_PNG        if figma_reference_attached
  + _APPEND_STACK            if stack_root (cleanTree root type STACK)
```

**Important:** `cleanTree`, tokens, and hints live in the **user** JSON (`client._generation_prompts`), not in system L6. Do not duplicate full `cleanTree` into system without removing it from user (doubles tokens, risks drift).

Optional Figma PNG: user message uses `REFERENCE_USER_PREAMBLE` + image block; system adds `_APPEND_FIGMA_PNG`.

## Repair — assembly

System: `_REPAIR_APR` with `string.Template.safe_substitute` (`$analyzeErrors`, `$code`, …).

Context built in `repair_scope.build_repair_environment_context`:

| Placeholder | Source |
|-------------|--------|
| `$code` | Full planned `.dart`, lines as `001\| …` |
| `$analyzeErrors` | Deduped bullet list |
| `$semanticHint` | JSON excerpt from `cleanTree` near `ValueKey('figma-…')`, else `null` |
| `$failedAttemptsHistory` | JSON array of prior failed patch dumps |
| `$unchangedWidgetNames` | JSON array |

User JSON: `mode: repair_patch`, `repairTargets[]`, `analyzeErrors`, `unchangedWidgetNames`.

## Visual refine — assembly

```
build_visual_refine_system_prompt()
  = build_system_prompt(figma_reference_attached=True, …)
  + _APPEND_REFINE
  + _APPEND_REFINE_SURGICAL   if surgical_widgets
```

User: three PNGs (fixed order) + labels from `USER_LABELS` / `visual_refine_attached_images()` metadata in JSON.

## Spec vs codebase (your supervisor doc)

### Roadmap

| Phase | Status |
|-------|--------|
| A | Done — token deficit, history JSON, font/controller, handbook |
| B | Done — `_SHARED_LAYOUT_RULES`, slim `_THEME_*` |
| C | Partial — `CONDITIONAL TEXT DISPATCH` in shared rules; CPI reserved (YAML flag TBD) |
| D | Pending — optional L1–L6 XML wrappers on themes (cosmetic, no L6 data in system) |

### Adopted / aligned

- Shared `_JSON_SCHEMA_GRAMMAR`, `_INTERACTIVE_RULES`, `_ROUTING_OFF`, `_SHARED_LAYOUT_RULES`.
- APR L1–L6 with `$` placeholders and `safe_substitute`.
- Line-numbered `$code` (`format_line_numbered_source`).
- `semanticHint` from Figma keys near error line.
- **TOKEN DEFICIT** (~150 lines → prefer `extractedWidget`) in `_REPAIR_APR`.
- **Controller lifecycle** and **font metric** rules in both theme bodies.
- `failedAttemptsHistory` serialized as JSON array (escapes quotes/newlines in Dart).

### Defer or do not copy verbatim

| Spec idea | Recommendation |
|-----------|----------------|
| L6 `{{cleanTree}}` / `{{tokens}}` in **generate** system | **Reject** — already in user JSON; use system for invariants only. |
| `<Thinking>` blocks in generate/repair output | **Risky** with strict JSON schema; providers may leak thinking into `screenCode`. If needed, use provider-native reasoning flags, not free-text tags. |
| Full L1–L6 rewrite of `_THEME_MATERIAL` | **Phased** — high churn; merge principles incrementally (done for controller/font). |
| **CPI supervisor** second LLM | **Not implemented** — needs schema, trigger (same errors + similar patches), injection point (prepend to repair user or system). See below. |
| `json.dumps(analyzeErrors)` in L6 | **Optional** — bullet list is more readable for models; keep unless logs break parsing. |
| `json.dumps(semanticHint)` when already JSON string | Already `json.dumps` for node list; do not double-encode. |

### CPI loop (future)

Trigger when: same analyzer lines after N repair attempts **and** patch similarity to `failedAttemptsHistory`.

Output schema (suggested): `{ "blindSpot": string, "directive": string }` — inject `directive` into next repair user message as `supervisorInterrupt`, not a second full system prompt.

Environment: `$lastPatches`, `$recurringErrors`, `$figmaNodeIntent` (subset of `semanticHint` / cleanTree contract).

## Prompt engineer checklist

| Symptom | Edit |
|---------|------|
| JSON fences / invalid schema | `_JSON_SCHEMA_GRAMMAR` |
| Dead buttons, no scroll | `_INTERACTIVE_RULES` |
| Wrong widget kit | `_THEME_MATERIAL` / `_THEME_CUPERTINO` |
| Router in screenCode | `_ROUTING_OFF` / `_APPEND_ROUTING` |
| PNG ignored on generate | `_APPEND_FIGMA_PNG` + `REFERENCE_USER_PREAMBLE` |
| STACK layout drift | `_APPEND_STACK` |
| Repair repeats same fix | L3 trajectory + `$failedAttemptsHistory` |
| Truncated repair JSON | L3 token deficit + split `extractedWidget` |
| Refine swaps images | `_APPEND_REFINE` + `USER_LABELS` order |
| Refine rewrites whole screen | `_APPEND_REFINE_SURGICAL` |

## Tests

```bash
poetry run pytest tests/test_repair_prompt_context.py tests/test_prompts_theme.py tests/test_visual_refine_loop.py tests/test_llm_repair.py -q
```
