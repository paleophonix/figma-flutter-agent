# Semantic IR Core and Layout Passes — Phase 1 (MVP)

| Field | Value |
| --- | --- |
| **Status** | Approved for implementation (Variant C — Strangler Fig) |
| **Owner** | Engineering |
| **Product reference** | `cash_change_layout` studio screen |
| **Last updated** | 2026-06-11 |

---

## 1. Purpose

Modernize the compiler middle-end so generation moves from low-level `Container` / `Padding` / absolute `Stack` output toward **deterministic semantic widgets** and **layout graph optimization passes**, without a full rewrite of the existing emit pipeline.

Phase 1 validates the mechanism on one reference layout (`cash_change_layout`) before expanding the remaining ~30 widget kinds from the backlog.

---

## 2. Architectural decision

**Approved approach:** Variant C (Strangler Fig).

- Extend `WidgetIrKind` and typed payload on `WidgetIrNode`.
- Hybrid classification: parser signals → LLM semantic tagging → deterministic IR passes.
- Jinja2 emission **only** for the seven MVP semantic kinds; legacy primitives continue through `render_node_body`.
- Register all future kinds in `WidgetIrKind` as stubs in Phase 1.

---

## 3. Critical architectural corrections

### 3.1. Graph drift prevention (mandatory)

**Problem:** Layout passes that mutate only `ScreenIr` are invisible to the legacy emit path, which reads geometry and layout modes from `CleanDesignTreeNode` via `render_node_body`.

**Requirement:**

- Every pass in `generator/ir/passes/` MUST apply **symmetric mutations** to:
  1. the matching `WidgetIrNode` (by `figmaId`), and
  2. the linked `CleanDesignTreeNode` in the indexed clean tree.
- Passes run inside the materialize path **before** `merge_screen_ir` and **before** any call to `render_layout_file` / `render_node_body`.
- After passes complete, `clean_tree` and `screen_ir` MUST agree on:
  - container kind / axis (`STACK` → `ROW` / `WRAP`),
  - `height_mode` / sizing (`FIXED` → `HUG` or min-height semantics),
  - `scroll_axis` when `NAV_SCROLL_HOST` is injected,
  - computed flex `spacing` metadata consumed by emit.

**Implementation contract:** introduce a single orchestrator (e.g. `apply_ir_layout_passes(screen_ir, clean_tree) -> tuple[ScreenIr, CleanDesignTreeNode]`) that owns dual-graph writes. Individual passes MUST NOT mutate one graph in isolation.

### 3.2. Macro-height scroll threshold

**Problem:** A default threshold of 850px falsely wraps standard 896px mobile artboards (`sign_up`, `music_v2`, `reminders`) in `NAV_SCROLL_HOST`, breaking CI goldens.

**Requirement:**

- Add `macro_height_threshold_px` to `ResponsiveConfig` in `config/models.py`.
- **Default: 900** (not 850).
- Override via `.ai-figma-flutter.yml` → `responsive.macro_height_threshold_px`.
- Document in `.ai-figma-flutter.yml.example`.

### 3.3. Payload modeling — Phase 1 vs technical debt

**Phase 1 (allowed):** flat `WidgetIrNode` with optional fields and `model_validator` guards keyed by `kind` (seven MVP types only).

**Technical debt (required before full taxonomy rollout):** when implementing the remaining 30+ kinds, refactor to a **polymorphic node hierarchy** split by domain (`INPUTS_DATA`, `ACTIONS_CONTROLS`, `NAVIGATION_LAYOUT`, `DATA_DISPLAY`, `OVERLAYS_FEEDBACK`). Do not grow a single 150-field monolith.

---

## 4. Middle-end pipeline (target)

```
Figma JSON
  │
  ▼
parser/tree.py ──► CleanDesignTreeNode
  │
  ├─► parser/interaction/* ──► interaction_signals (hints only, not final kind)
  │
  ▼
stages/llm.py ──► ScreenIr (LLM assigns semantic WidgetIrKind on nodes)
  │
  ▼
generator/ir/materialize.py
  │
  ├─► validate_screen_ir (existing)
  ├─► apply_ir_layout_passes(screen_ir, clean_tree)   ◄── NEW (dual-graph)
  │     ├─ unstack_homogeneous_stack
  │     ├─ unpin_cascaded_heights
  │     └─ inject_scroll_host (macro_height_threshold_px)
  ├─► merge_screen_ir (existing)
  │
  ▼
emit branch
  ├─ semantic WidgetIrKind (MVP set) ──► emit_semantic_widget() ──► Jinja2 templates
  └─ legacy kind (column, row, stack, auto, …) ──► render_node_body(clean_tree)
  │
  ▼
planner / writer ──► Dart files
```

**Orchestration note:** `stages/plan.py` remains a thin stage entry; pass invocation lives in `materialize_screen_code_from_ir` (or a dedicated submodule called from it). `generator/planner/plan.py` is unchanged except for consuming already-synchronized graphs.

---

## 5. MVP widget taxonomy

### 5.1. Fully implemented (schema + pass hooks + Jinja2 emit)

| `WidgetIrKind` | Flutter target | Key payload fields |
| --- | --- | --- |
| `INPUT_TEXT_FIELD` | `TextFormField` | `hintText`, `errorText`, `isMultiline`, `maxLines` |
| `BUTTON_FILLED` | `ElevatedButton` | label via overrides / child text |
| `CHIP_CHOICE` | `ChoiceChip` | `isSelected: bool` (required) |
| `CONTAINER_CARD` | `Container` + `BoxDecoration` | shadows, radius, inner flex |
| `CONTAINER_LIST_TILE` | `ListTile` anatomy | leading / title / subtitle / trailing |
| `NAV_SCROLL_HOST` | `SingleChildScrollView` | axis, child ref |
| `TECHNICAL_DIVIDER` | `Divider` | — |

### 5.2. Enum stubs only (backlog)

All remaining kinds from the epic spec (e.g. `INPUT_SEARCH_BAR`, `BUTTON_FAB`, `NAV_APP_BAR`, `OVERLAY_DIALOG`, `FEEDBACK_SKELETON`, …) MUST be registered in `WidgetIrKind` but MUST NOT emit Dart in Phase 1. Stub kinds fall back to `AUTO` with a coverage warning, or fail in strict mode per existing generation policy.

### 5.3. Theme variant

- Default: **Material 3** (`theme.variant: material_3`).
- Cupertino widgets (`CupertinoSwitch`, etc.) ONLY when `theme.variant: cupertino`.
- No shape-based heuristics.

### 5.4. `FEEDBACK_SKELETON`

T3 stub + design-coverage warning. No `shimmer` package or `pubspec.yaml` mutation in Phase 1.

---

## 6. Layout pass specifications

### 6.1. Unstacking / row-collapse pass

**Trigger:** `WidgetIrNode.kind == stack` (mirrored `NodeType.STACK` on clean tree) whose children are **homogeneous** semantic components (same `WidgetIrKind` or same classifiable `NodeType`).

**Transform criteria (all required):**

- Vertical overlap delta ≤ **1.0 px** across children.
- Monotonic increase of child `x` (horizontal row) without bounding-box overlap (tolerance ≤ **0.5 px**).
- Zero effective Z-overlap (stack used as false absolute layout).

**Action (dual-graph):**

- Rewrite parent to `row` or `wrap` on both IR and clean tree.
  - Use `wrap` when summed child widths + gaps exceed parent width.
- Reset child coordinates to relative flex layout; clear absolute `stack_placement` where applicable.
- Compute spacing deterministically:

  ```
  spacing[i] = child[i+1].x - child[i].x - child[i].width
  ```

- Persist `spacing` on the parent node metadata for emit (IR + clean tree layout slot).

**Regression anchor:** quick-sum chip block pattern from `cash_change_layout` (Figma id `362:54` in reference dump). Pass logic MUST remain id-generic; `362:54` is a fixture reference only.

### 6.2. Height unpinning pass

**Trigger:** cascaded `height_mode: FIXED` on column hosts containing text or adaptive children.

**Action (dual-graph):**

- Promote rigid heights to `minHeight` semantics (`ConstrainedBox`) or flex children (`Flexible` / `Expanded` hints).
- Block emission of hard `SizedBox(height: …)` for unpinned nodes.
- Mirror `height_mode` changes on clean tree `sizing` fields.

### 6.3. Macro scroll host pass (`NAV_SCROLL_HOST`)

**Trigger:** root vertical extent **>** `responsive.macro_height_threshold_px` (default **900**).

**Action (dual-graph):**

- Strip root fixed height flags.
- Wrap root subtree in `NAV_SCROLL_HOST` / `SingleChildScrollView` on both graphs.
- Set `scroll_axis` appropriately on clean tree.

---

## 7. Parser and LLM layers

### 7.1. Parser (`parser/interaction/`)

Deterministic signal extraction only:

- corner radii, pill heights, icon glyphs (clear, search, minus/plus),
- layer-name regex hints,
- homogeneity metrics for sibling groups.

Signals are attached as metadata for the LLM payload; they do NOT assign final `WidgetIrKind` alone.

### 7.2. LLM (`stages/llm.py`, `llm/prompts/`, structured schema)

- Extend strict JSON schema for new `WidgetIrKind` values and MVP payload fields.
- Update `dump_screen_ir_blueprint` and systemic rules in `llm/prompts.py` where needed.
- Model assigns semantic kinds using blueprint + interaction signals + neighborhood context.

---

## 8. Emission layer

### 8.1. Jinja2 dispatcher

- New module: `generator/ir/semantic_emit.py` (name may vary) exposing `emit_semantic_widget(ir, clean, ctx)`.
- Templates: `generator/templates/widgets/<kind_snake>.dart.j2` for each MVP kind.
- **Prohibited:** raw Dart string literals for MVP semantic kinds inside Python emit modules.
- Legacy path unchanged for non-MVP kinds.

### 8.2. Integration point

`generator/ir/expression.py` → `emit_widget_expression`:

```
if ir.kind in SEMANTIC_MVP_KINDS:
    return emit_semantic_widget(...)
return render_node_body(clean, ...)
```

---

## 9. Fixtures and test strategy

### 9.1. Corpus localization

| Artifact | Path | Source |
| --- | --- | --- |
| Full screen dump | `tests/fixtures/layouts/cash_change_layout.json` | Copy from `e:/@dev/flutter-demo-project/ataev/.debug/raw/cash_change_layout.json` |
| Manifest entry | `tests/fixtures/screens.yaml` | Deferred: raw Figma dump is not a `CleanDesignTreeNode` JSON; tests load via `build_clean_tree` |
| Tests | `tests/test_cash_change_layout.py` | Remove hard-coded external `_DUMP` path; load via `fixtures_root()` |

### 9.2. Pass unit tests

- Synthetic IR + clean-tree fixtures under `tests/fixtures/ir/` (or inline builders in tests).
- Cover unstacking math independently of full emitter integration.
- Do NOT hardcode `362:54` inside pass implementation; use generic homogeneous-stack geometry.

### 9.3. Regression guards

- Existing fixtures at 896px height MUST NOT gain root `SingleChildScrollView` after macro scroll pass.
- `poetry run pytest -q -m "not live_figma"` MUST stay green.
- Generated `cash_change` layout MUST pass `dart analyze` when run through full pipeline.

---

## 10. Module touch map

| Area | Paths |
| --- | --- |
| IR schema | `src/figma_flutter_agent/schemas/ir.py`, `schemas/__init__.py` |
| IR passes | `src/figma_flutter_agent/generator/ir/passes/` (new package) |
| Materialize hook | `src/figma_flutter_agent/generator/ir/materialize.py` |
| Expression dispatch | `src/figma_flutter_agent/generator/ir/expression.py` |
| Semantic templates | `src/figma_flutter_agent/generator/templates/widgets/*.j2` |
| Config | `src/figma_flutter_agent/config/models.py`, `.ai-figma-flutter.yml.example` |
| Parser signals | `src/figma_flutter_agent/parser/interaction/` |
| LLM schema / prompts | `src/figma_flutter_agent/llm/clients/`, `llm/prompts/` |
| Fixtures | `tests/fixtures/layouts/`, `tests/fixtures/screens.yaml`, `tests/test_cash_change_layout.py` |

---

## 11. Acceptance criteria (Phase 1)

1. **Static analysis:** generated code for `cash_change_layout` passes `dart analyze`.
2. **Unstacking:** quick-sum block (`362:54` in reference dump) emits a clean `Wrap` (or `Row`) with computed `spacing`; no overlapping `Positioned` widgets for that block.
3. **Scroll threshold:** default `macro_height_threshold_px = 900`; `sign_up`, `music_v2`, `reminders` fixtures do not spuriously wrap in `NAV_SCROLL_HOST`.
4. **Drift:** after passes, legacy `render_node_body` observes updated `clean_tree` geometry (verified by unit test on dual-graph sync).
5. **Template isolation:** all seven MVP kinds render exclusively via Jinja2 templates.
6. **CI:** offline pytest suite green; no dependency on local demo-project paths.

---

## 12. Out of scope (Phase 1)

- Full implementation of 30+ stub `WidgetIrKind` values.
- `FEEDBACK_SKELETON` shimmer package integration.
- Replacing all legacy emit with Jinja2.
- Polymorphic IR node hierarchy (tracked as tech debt — §3.3).
- Screen-specific conditionals, hardcoded Figma ids, or per-customer layout hacks in `src/`.

---

## 13. Technical debt register

| ID | Item | Trigger |
| --- | --- | --- |
| TD-IR-01 | Polymorphic `IRNode` hierarchy by domain | Start of Phase 2 (types 8–40+) |
| TD-IR-02 | Migrate remaining emit from Python f-strings to Jinja2 | Post-MVP stabilization |
| TD-IR-03 | `FEEDBACK_SKELETON` real shimmer + pubspec injection | Separate epic |

---

## 14. Implementation checklist

### Block A — Schema and config

- [x] **A1.** Extend `WidgetIrKind` with all epic kinds; mark non-MVP values as stub in emit dispatcher.
- [x] **A2.** Add MVP payload fields to `WidgetIrNode` with `model_validator` per kind (seven types only).
- [x] **A3.** Add `ResponsiveConfig.macro_height_threshold_px: int = 900` and YAML example entry.
- [x] **A4.** Update LLM strict JSON schema and blueprint dump for new kinds / payload.

### Block B — Dual-graph passes

- [x] **B1.** Create `generator/ir/passes/` package with `apply_ir_layout_passes` orchestrator.
- [x] **B2.** Implement `unstack_homogeneous_stack` (criteria §6.1) with symmetric IR + clean-tree writes.
- [x] **B3.** Implement `unpin_cascaded_heights` (§6.2) with symmetric writes.
- [x] **B4.** Implement `inject_scroll_host` using `macro_height_threshold_px` (§6.3).
- [x] **B5.** Wire passes into `materialize_screen_code_from_ir` and `plan_generation_files` (before layout emit).
- [x] **B6.** Unit tests: synthetic fixtures for each pass; dual-graph sync assertion.

### Block C — Parser and LLM hints

- [x] **C1.** Add interaction signal metadata from `parser/interaction/` into LLM payload (generic signals only).
- [x] **C2.** Update generation prompts with semantic kind rules for MVP set.
- [ ] **C3.** Add systemic NEVER/MUST rule to `SYSTEMIC_BUG_RULES` if recurring mis-tags appear.

### Block D — Semantic Jinja2 emit

- [x] **D1.** Create `generator/templates/widgets/` with seven `.dart.j2` templates (Material 3 default; Cupertino branch via config).
- [x] **D2.** Implement `emit_semantic_widget()` dispatcher.
- [x] **D3.** Integrate dispatcher in `emit_widget_expression`.
- [x] **D4.** Stub kinds: warning / strict fallback policy without Dart emission.

### Block E — Fixtures and acceptance

- [x] **E1.** Copy `cash_change_layout.json` into `tests/fixtures/layouts/`.
- [ ] **E2.** Register `cash_change` in `tests/fixtures/screens.yaml` (blocked: needs clean-tree export, not raw Figma JSON).
- [x] **E3.** Refactor `tests/test_cash_change_layout.py` to use fixture corpus (no external paths).
- [x] **E4.** Add test: quick-sum block emits `Wrap`/`Row` with spacing, no overlapping `Positioned`.
- [x] **E5.** Add test: 896px fixtures unaffected by macro scroll pass.
- [x] **E6.** Run targeted pytest suite for IR MVP modules.

### Block F — Documentation

- [x] **F1.** Update module READMEs for touched packages (`generator/ir/passes/`, semantic emit).
- [x] **F2.** Mark checklist items complete in this file as work progresses.

---

## 15. S6 entry criteria

Implementation (S6) MAY begin only when:

- This document is committed under `docs/projects/semantic-ir-layout-passes/`.
- Product/architecture corrections in §3 are accepted without further debate on threshold (900px) or dual-graph sync.

---

## 16. Revision history

| Date | Change |
| --- | --- |
| 2026-06-11 | Initial S5 plan; Variant C approved; drift prevention, 900px threshold, polymorphic tech debt |
