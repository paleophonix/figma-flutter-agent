# LLM repair & visual refine loop

Status: **Phase 1 implemented**  
Owner: figma-flutter-agent  
Last updated: 2026-05-26

---

## S1 — Goal (SMART)

After the primary LLM codegen pass, automatically **repair or refine** generated Dart when validation fails or visual fidelity is poor — **before** committing files to the Flutter project.

| Dimension | Target |
|-----------|--------|
| **Specific** | Two optional post-gen LLM stages: **analyze repair** and **visual refine** |
| **Measurable** | Repair loop clears `dart analyze` errors within ≤2 attempts on fixture screens; visual pass reduces pixel diff below configured threshold when enabled |
| **Achievable** | Reuse existing `FlutterGenerationResponse` schema, `validate_planned_dart_files`, Figma reference PNG, golden PNG |
| **Relevant** | Unblocks wizard `run` when LLM emits invalid Dart (e.g. `music_v2`) |
| **Time-bound** | Phase 1 (repair) shippable first; Phase 2 (visual) follows golden automation |

### Definition of Done (Phase 1 — repair)

- [x] Config flags in `.ai-figma-flutter.yml` + env documented
- [x] Repair runs **after render/plan, before write** when analyze fails on planned files
- [x] Context: clean tree JSON, tokens, asset manifest, widget/navigation hints, current `screenCode` + `extractedWidgets`, **analyze error text**
- [x] Same structured output schema as primary LLM; postprocess applied after each attempt
- [x] Hard cap `llm_repair_max_attempts` (default 2); logs each attempt
- [x] Tests: unit (prompt payload), integration (mock LLM + planned files → green analyze)
- [ ] `./scripts/signoff.ps1` green

### Definition of Done (Phase 2 — visual refine)

- [x] Optional pass after analyze OK when `llm_visual_refine: true`
- [x] Flutter PNG captured via golden test (`test/goldens/{feature}_screen.png`) before each compare
- [x] Context adds Figma reference PNG + Flutter result PNG + pixel diff summary (text)
- [x] Iterative loop: compare → refine → re-plan → analyze → re-capture → compare (≤ `llm_visual_refine_max_attempts`)
- [x] Stops early when diff ratio ≤ `llm_visual_refine_threshold` (default 0.08)
- [ ] `visual-qa compare` documents end-to-end flow

---

## S2 — Affected modules

| Module | Change |
|--------|--------|
| `config.py` | `GenerationConfig`: repair/refine flags |
| `.ai-figma-flutter.yml.example` | defaults + comments |
| `llm/prompts.py` | `build_repair_system_prompt`, `build_visual_refine_system_prompt` |
| `llm/client.py` | optional `analyze_errors` text param; multimodal (2 PNGs) for visual pass |
| `stages/llm_repair.py` | **new** — repair/refine orchestration |
| `pipeline/__init__.py` | insert repair loop between `plan` and `write` |
| `generator/validation.py` | export `parse_analyze_errors(details) -> list[str]` (optional helper) |
| `generator/renderer.py` | re-render planned files after repair response |
| `validation/compare.py` | reuse pixel diff for threshold gate |
| `dev/wizard.py` | inherit repair loop on `sync_preview` |
| `tests/test_llm_repair*.py` | **new** |

**Not in scope:** `screens.yaml` in LLM context (see below).

---

## S3 — Practices

- Structured output: same `FlutterGenerationResponse` + `generation_json_schema(strict=…)` as primary pass
- Always run `postprocess_generated_dart` after repair output
- Preserve `// <custom-code>` zones; repair prompt must forbid deleting them
- Log repair attempts with `loguru` (`stage=llm_repair`, `attempt=N`)
- Reasoning settings: reuse `LLM_REASONING_*` env; repair may use `effort=medium`, visual `effort=high`
- Fail open on repair LLM error → fall through to existing write failure (no silent skip unless configured)

---

## S4 — Architecture

### Pipeline placement (Phase 2 — after repair)

```
… analyze repair loop OK …
  ↓ llm_visual_refine + generate_golden_test
  capture golden → compare vs Figma reference
  ↓ diff > threshold
  visual refine LLM (2 PNGs) → re-plan → analyze → capture → compare (loop ≤ N)
  ↓ diff ≤ threshold OR attempts exhausted
write
```

**Stop conditions (visual loop):**

1. `changedRatio <= llm_visual_refine_threshold` → success, proceed to write
2. `refine_attempts >= llm_visual_refine_max_attempts` → warning, proceed to write (fail open)
3. golden capture / LLM / analyze failure → warning, keep last good planned files

Each iteration always **re-compares** after refine; there is no blind single-shot refine.

### Pipeline placement (Phase 1)

```
fetch → parse → LLM (primary) → plan/render → validate_planned (analyze)
  ↓ errors + llm_repair_after_analyze
  repair LLM → re-render → postprocess → analyze (loop ≤ N)
  ↓ OK or exhausted
write (existing commit_planned_files)
```

**Critical:** analyze loop uses **`validate_planned_dart_files`** (temp skeleton) — same as spec23 — so we **do not write** broken Dart to `demo_app` during repair.

Today analyze runs **inside write** (`commit_planned_files`). Phase 1 refactors:

1. Extract **pre-write analyze** call on `planned_files` dict (full planned set, not only `files_to_write` subset when LLM screen regen).
2. On failure → repair loop → update `planned_files` in memory.
3. Write stage keeps final analyze as safety net (idempotent).

### Two passes (not one mega-prompt)

| Pass | Trigger | Images | Primary signal |
|------|---------|--------|----------------|
| **Repair** | `dart analyze` errors on planned files | Figma PNG optional | Error lines from analyze stderr |
| **Visual refine** | analyze OK + diff > threshold | Figma PNG + Flutter PNG | Pixel diff % + optional top-level layout hints |

### Context payload (JSON user message)

```json
{
  "mode": "repair" | "visual_refine",
  "featureName": "music_v2",
  "cleanTree": { },
  "tokens": { },
  "assetManifest": [ ],
  "widgetExtractionHints": [ ],
  "navigationHints": [ ],
  "currentGeneration": {
    "screenCode": "...",
    "extractedWidgets": [ ]
  },
  "analyzeErrors": [ "error - lib/.../music_v2_screen.dart:378:8 - ..." ],
  "visualDiff": {
    "changedRatio": 0.12,
    "passed": false,
    "threshold": 0.08
  }
}
```

### `screens.yaml` — decision

**Do not include** in LLM context for single-screen repair.

| Include | Reason |
|---------|--------|
| `cleanTree`, `tokens`, `assetManifest` | Already in pipeline context |
| `navigationHints` | Routing/prototype links (replaces batch manifest for LLM) |
| `featureName`, `nodeId` | From parsed URL / pipeline |

| Exclude | Reason |
|---------|--------|
| Full `screens.yaml` | Batch ops metadata; duplicates `file_key` / `node_id` |
| Raw Figma dump JSON | Too large; clean tree is the contract |

**Exception (future):** multi-screen routing repair may pass **`navigationHints` only** derived from manifest, not raw YAML.

### Flutter PNG capture (Phase 2)

Prerequisites:

- `validation.generate_golden_test: true` (emits `test/golden/{feature}_screen_test.dart`)
- Subprocess: `flutter test test/golden/{feature}_screen_test.dart --update-goldens` in `project_dir`
- Output: `test/goldens/{feature}_screen.png`

Optional later: headless `integration_test` screenshot — out of Phase 2 scope.

Cache key: `sha256(planned_dart + clean_tree_hash)` → skip re-golden if unchanged.

---

## S5 — Config

### YAML (`.ai-figma-flutter.yml`)

```yaml
generation:
  # Phase 1 — default ON when use_deterministic_screen: false
  llm_repair_after_analyze: true
  llm_repair_max_attempts: 2
  llm_repair_include_figma_png: false   # optional vision on repair pass

  # Phase 2 — default OFF (cost/latency); iterative compare → refine → compare loop
  llm_visual_refine: false
  llm_visual_refine_max_attempts: 2   # compare/refine cycles; stops early when diff <= threshold
  llm_visual_refine_threshold: 0.08   # pixel diff ratio; skip refine when initial compare is below
  llm_visual_refine_capture_golden: true  # run flutter test --update-goldens before each compare
```

### Env

No new required env vars. Reuses `LLM_*`, reasoning, API keys.

---

## S6 — Prompts (sketch)

### Repair system prompt (extends base Material rules)

```
REPAIR MODE:
You receive the current FlutterGenerationResponse that FAILED dart analyze.
Your job is to emit a CORRECTED response with the same schema.

Rules:
1. Fix ONLY issues listed in analyzeErrors (and obvious dependencies).
2. Do NOT refactor working layout; minimal diff mindset.
3. Preserve ALL // <custom-code> ... // </custom-code> blocks verbatim.
4. Do NOT add imports — the template injects them.
5. Honor compiler invariants from the primary prompt (Alignment, textScaler, etc.).
6. If analyzeErrors mention extracted widget files, fix those widgets in extractedWidgets.
```

User preamble when Figma PNG attached: same golden-standard block as primary pass.

### Visual refine system prompt

```
VISUAL REFINE MODE:
Attached images: (1) Figma golden standard, (2) current Flutter render.
JSON cleanTree/tokens define structure; images define appearance.

Adjust layout, spacing, typography, and colors to reduce visual gap.
Do NOT break analyze-clean Dart. Minimal structural change.
Prefer token/theme usage over hardcoded literals.
```

User message includes `visualDiff.changedRatio` when available.

---

## S7 — Implementation checklist

### Phase 1 — Analyze repair loop

- [x] **1.1** Add `GenerationConfig` fields + validators in `config.py`
- [x] **1.2** Update `.ai-figma-flutter.yml.example` and agent repo `.ai-figma-flutter.yml` comment block
- [x] **1.3** Add `parse_analyze_errors()` helper in `generator/validation.py` (split stderr into error lines)
- [x] **1.4** Add `build_repair_system_prompt()` + repair user payload builder in `llm/prompts.py` / `llm/repair.py`
- [x] **1.5** Extend `LlmClient` / stage with `repair_async(...)` on `BaseLlmClient`
- [x] **1.6** Create `stages/llm_repair.py`:
  - [x] `run_analyze_repair_loop(request) -> LlmRepairStageResult`
  - [x] inputs: settings, llm client factory, planned_files, pipeline context artifacts, primary `FlutterGenerationResponse`
  - [x] loop: analyze → repair LLM → re-plan/re-render subset → postprocess → analyze
- [x] **1.7** Wire in `pipeline/__init__.py` after `validate_planned_generation`, before write
- [x] **1.8** Log `stage=llm_repair` attempt count; surface warning if exhausted
- [x] **1.9** Tests:
  - [x] `test_llm_repair.py` — payload shape, prompt contains analyze errors
  - [x] `test_llm_repair.py` — mock client fixes fixture with intentional error
- [ ] **1.10** Manual: wizard `run` on `music_v2` with repair enabled

### Phase 2 — Visual refine

- [x] **2.1** Add `capture_planned_flutter_golden_png()` helper (`validation/golden_capture.py`)
- [x] **2.2** Gate on pixel diff ratio vs threshold; `compare_png_bytes()` for in-memory compare
- [x] **2.3** Add `build_visual_refine_system_prompt()` + dual-image `visual_refine_async`
- [x] **2.4** Integrate iterative loop in `stages/visual_refine.py` after repair, before write
- [x] **2.5** Tests in `tests/test_visual_refine_loop.py`
- [ ] **2.6** Document wizard + `visual-qa compare` flow in `llm/README.md`

### Phase 3 — Hardening (optional)

- [ ] Cache golden PNG by content hash
- [ ] Metrics: repair attempt count, success rate (PostHog / logs)
- [ ] Production profile: `llm_repair_after_analyze: true`, `llm_visual_refine: false`

---

## S8 — Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Repair rewrites entire screen | Prompt + “minimal diff”; compare line count delta in tests |
| Infinite cost | Hard caps; repair without PNG by default |
| Golden capture flaky in CI | Phase 2 off in CI; repair-only in signoff |
| Temp-dir analyze ≠ real project | Final analyze in write stage retained |
| LLM ignores custom zones | `strict_preservation` still applies at write |

---

## S9 — Out of scope (v1)

- Feeding `screens.yaml` to LLM
- Device/runtime screenshots (`flutter run`)
- Automatic pixel-diff image as third vision input (text summary only v1)
- Repair for deterministic codegen path (LLM repair only when primary was LLM)

---

## S10 — Manual test plan

1. Enable `use_deterministic_screen: false`, `llm_repair_after_analyze: true`
2. Wizard → `music_v2` → full run
3. If primary LLM emits bad Dart, logs show `llm_repair attempt 1/2`
4. Write succeeds; `dart analyze` clean on generated files
5. (Phase 2) Enable golden + visual refine; compare reports lower diff after refine
