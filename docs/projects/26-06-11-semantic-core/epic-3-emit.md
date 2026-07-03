# EPIC 3 — Typed Emit (Jinja2)

**Source:** [semantic-core.md](semantic-core.md) (EPIC 3)  
**Prerequisite:** [epic-2.5-safety.md](epic-2.5-safety.md)

## S1 — Goal (locked)

**Why:** E2 writes semantic `kind` into IR; E2.5 keeps Dart bit-identical via `report_only`. EPIC 3 unlocks **verified semantic rendering** through Jinja2 templates, typed payload, golden proof, and per-node `fidelityTier` — without Dart string sniffing in Python.

**What (DoD):** template-only semantic emit path; blocking CI lint «no Dart in Python»; semantic kind changes Dart only when tier + golden allow; fallback preserves pixels and IR annotation.

**Out of scope:** new detectors (E2), safety envelope (E2.5), graph middle-end (E4), full sniffing burn-down to zero (E5).

---

## S2 — Codebase map (existing components)

### Pipeline (screen IR path today)

```text
materialize_screen_code_from_ir (generator/ir/materialize.py)
  → apply_ir_layout_passes
  → apply_ir_classification_passes (parser/semantics/classify.py)
  → run_cp_post_classify (geometry/invariants/checkpoints.py)
  → emit_screen_code_from_ir (generator/ir/screen.py)
       → merge_screen_ir (generator/ir/tree.py)     # structure only; kind not consumed here
       → emit_merged_root_expression (expression.py) # ⚠ calls render_node_body only
       → screen_shell_dart (layout/cupertino.py)
```

Parallel **deterministic layout** path (unchanged by E2/E2.5): `generator/planner/` → `render_layout_file` → `generator/layout/widgets/emit/dispatch.py` (`render_node_body`).

### Critical gap (E3 must close)

| Function | Semantic branch | Wired into screen emit? |
| --- | --- | --- |
| `emit_widget_expression` | Yes — outer gate + `emit_semantic_widget` | **No** — only `tests/test_semantics_emit_gate.py` |
| `emit_merged_root_expression` | No — always `render_node_body(merged_clean)` | **Yes** — production screen body |

**Implication:** flipping `report_only=false` today does **not** change generated screen Dart. E3 must add IR-aware recursive emit (`screen_ir` + `clean_tree` walk) and route each node through `emit_widget_expression` (then E3.5 inner tier router).

### Module touch map

| Layer | Path | Role in E3 | E3 wave |
| --- | --- | --- | --- |
| **Outer emit gate** | `generator/ir/expression.py` (`_semantic_mvp_emit_enabled`, `emit_widget_expression`) | Master kill-switch; semantic vs geometric per node | E3.5 (+ wire screen) |
| **Screen shell** | `generator/ir/screen.py` | Replace `emit_merged_root_expression` with IR walk | E3.1 |
| **IR merge** | `generator/ir/tree.py` (`merge_screen_ir`, `merge_ir_node`) | Child order / EXTRACTED refs; no kind emit today | E3.1 (pair with emit walk) |
| **Semantic Jinja** | `generator/ir/semantic_emit.py` | `_TEMPLATE_BY_KIND`, thin `_build_template_context` | E3.1–E3.2 |
| **Templates** | `generator/templates/widgets/*.dart.j2` (7 MVP files) | Native widget fragments | E3.1 |
| **Template infra** | `generator/renderer.py`, `templates/screen.dart.j2` | Screen class shell; not semantic bodies | reference |
| **Geometric fallback** | `generator/layout/widgets/emit/dispatch.py` + 33 modules under `layout/widgets/` | `render_node_body` — heavy inline Dart strings | E3.4 burn-down target |
| **IR schema** | `schemas/ir.py` (`WidgetIrKind`, `WidgetIrNode`, kind sets) | 7 MVP + ~36 stub semantic kinds; **no `fidelity_tier`** | E3.3 |
| **Payloads** | `schemas/ir_payloads.py` | `ChipChoicePayload`, `InputTextFieldPayload`, `GenericSemanticPayload` | E3.1–E3.2 |
| **Classifier** | `parser/semantics/` (`classify.py`, detectors, `prefilter.py`) | Writes `kind` + `payload`; `SEMANTIC_IR_KINDS` ≈ all non-layout kinds | read-only for E3 |
| **Materialize** | `generator/ir/materialize.py` | Orchestrates classify → emit; no emit logic | wire only |
| **Config** | `config/models.py` → `SemanticsSettings.report_only` | Outer gate default `true` | retained |
| **Emit context** | `generator/ir/context.py` (`IrEmitContext.semantic_report_only`) | Per-run override for tests | retained |
| **Golden / pixel** | `validation/golden_capture.py`, `stages/visual_refine.py`, `fixtures/golden_planned.py` | Exists; not per-kind tier promotion yet | E3.2–E3.3 |
| **CI lint** | `tests/test_dart_postprocess_inv6.py` | INV-6: no `Positioned`/`Stack` regex in postprocess only | E3.4 expands scope |

### Kind inventory (schema)

| Set | Count | Location |
| --- | ---: | --- |
| `SEMANTIC_MVP_IR_KINDS` | 7 | `schemas/ir.py` — templates exist |
| `SEMANTIC_IR_KINDS` (classifier) | ~43 | `parser/semantics/prefilter.py` — enum minus layout kinds |
| `STUB_IR_KINDS` | ~36 | `schemas/ir.py` — warn + geometric fallback in `emit_widget_expression` |
| MVP templates on disk | 7 | `generator/templates/widgets/` — 1:1 with MVP kinds |

### Tests (existing vs E3 target)

| Test | Covers |
| --- | --- |
| `tests/test_semantics_emit_gate.py` | Outer gate on **isolated** `emit_widget_expression` |
| `tests/test_semantic_emit.py` | Direct `emit_semantic_widget` template smoke |
| `tests/test_semantics_materialize.py` | Classify runs before emit (mocked emit) |
| `tests/test_cp_post_classify.py` | Checkpoint after classify |
| *Missing* | Screen-level semantic emit, `fidelity_tier` router, template golden per kind, E3.4 Dart-in-Python lint |

### E3 integration seams (where code lands)

1. **E3.1** — `screen.py` + new `emit_ir_subtree` (or extend `expression.py`): walk `ScreenIr.root` parallel to `index_clean_tree`, delegate children to `emit_widget_expression`.
2. **E3.2** — Enrich `_build_template_context` from `clean.style` / tokens; golden compare semantic vs geometric per fixture kind.
3. **E3.3** — `WidgetIrNode.fidelity_tier` in `schemas/ir.py` + classifier/materialize stamping from corpus; downgrade on golden failure.
4. **E3.4** — Blocking lint: Dart widget literals outside `generator/templates/` whitelist (layout emit is primary debt).
5. **E3.5** — `route_by_fidelity_tier(ir)` **inside** the semantic branch of `emit_widget_expression`, after `_semantic_mvp_emit_enabled(ctx)` (Variant B — do not collapse).

---

## S4 — Solution concept (approved)

Three design forks for EPIC 3. **Chosen:** **A + hybrid tier manifest + incremental lint** (below).

### Fork 1 — Screen emit wiring (how IR reaches Dart)

| Option | Idea | Pros | Cons | Verdict |
| --- | --- | --- | --- | --- |
| **A. IR-primary recursive emitter** | New `emit_ir_subtree(ir, clean, ctx)` in `expression.py`; `screen.py` calls it instead of `emit_merged_root_expression`. Layout containers: children from IR walk; reuse `render_column` / `render_row` / `render_stack` with **pre-built** `child_widgets`. Geometric fallback: `render_node_body` only when `ir.children` is empty (leaf). | Matches IR child order; `emit_widget_expression` becomes the single per-node router; extracted + semantic + geometric share one walk; minimal duplication with E2.5 gate tests | Requires splitting “container vs leaf” in geometric fallback; first wave touches `screen.py` + `extracted.py` | **✅ Selected** |
| **B. Dispatch hook only** | Pass custom `recurse` into `render_node_body` from `screen.py`; hook calls `emit_widget_expression` per child | Smaller diff at entry point | `emit_widget_expression` today calls full `render_node_body(clean)` on non-semantic nodes → **double subtree** or wrong child order; hook fights 500+ lines of dispatch heuristics | ❌ Reject |
| **C. Post-hoc AST / string splice** | Geometric screen first; sidecar or regex swaps semantic regions | No emit refactor | Violates universal-codegen + anti-patching; brittle with layout heuristics | ❌ Reject |

**A — target flow:**

```text
emit_screen_code_from_ir
  → merge_screen_ir (structure / omit / stack order — unchanged)
  → emit_ir_subtree(screen_ir.root, merged_root, ctx)
       for each ir_child + clean_child:
         emit_widget_expression (existing router)
           semantic branch: tier router → Jinja
           layout branch (COLUMN/ROW/STACK/AUTO→clean.type): emit_ir_subtree children → layout shell
           leaf geometric: render_node_body(clean)  # no child recursion
```

`extracted.py` uses the same `emit_ir_subtree` entry (today also stuck on `emit_merged_root_expression`).

### Fork 2 — `fidelity_tier` authority (when native emit is allowed)

| Option | Idea | Pros | Cons | Verdict |
| --- | --- | --- | --- | --- |
| **A. Kind manifest + per-node downgrade** | `tests/fixtures/semantics/fidelity_manifest.yaml`: kind → default tier + corpus fixture ids. `stamp_fidelity_tiers()` pass in `materialize.py` after classify. Instance golden failure → downgrade node to `native_unverified` / geometric, keep `kind`. | Fast `generate`; promotion is CI-gated; per-kind rollout (E5) without reclassify | Manifest must stay in sync with template goldens | **✅ Selected** |
| **B. Runtime golden on every generate** | Pixel-diff each semantic node during `materialize` | Always fresh | Too slow; needs Flutter render in hot path; flaky in dev | ❌ Reject |
| **C. Classifier stamps tier** | Detectors set `fidelity_tier` with confidence | Single pass | Conflates detection truth with render proof; violates E2/E3 separation | ❌ Reject |

**Tier router (E3.5)** stays in `emit_widget_expression` **after** outer `report_only` gate:

```text
native_verified     → emit_semantic_widget
native_unverified   → render_node_body (leaf) / strict profile error
svg_baked/png_baked → asset emit (existing vector/raster paths)
unsupported         → geometric leaf
report_only=true    → skip entire semantic branch (E2.5-I)
```

Default for classified semantic nodes without manifest entry: **`native_unverified`** (geometric Dart, kind preserved).

### Fork 3 — Style payload + CI lint (E3.2 / E3.4)

| Option | Idea | Pros | Cons | Verdict |
| --- | --- | --- | --- | --- |
| **A. `StyleContext` builder → Jinja** | `generator/ir/style_context.py` maps `clean.style` + tokens → typed template dict (colors, radii, padding, typography slots). Templates own Material suppression (`minimumSize`, `tapTarget`, theme overrides). | Single style contract; testable without full screen | Upfront schema for template context | **✅ Selected** |
| **B. Reuse layout Python decorators inline** | Call existing `BoxDecoration` string builders from `layout/widgets/decoration.py` inside `semantic_emit.py` | Faster MVP | Keeps Dart in Python; blocks E3.4; two style paths | ❌ Reject (MVP-only debt) |
| **C. Big-bang lint** | CI fails on any `Container(` in `layout/` | Clean end state | 33 modules / ~144 sniff sites — blocks all E3 delivery | ❌ Reject |

**E3.4 lint:** `scripts/lint_dart_in_python.py` — **blocking** for new violations outside whitelist; **burn-down metric** for existing `layout/widgets/` (count must not increase; decreases tracked per wave). Whitelist: `generator/templates/**`, narrow core (`layout/common.py`, geometry literals), AST sidecar.

### Wave ordering (derived from chosen concept)

| Wave | Delivers | Depends on |
| --- | --- | --- |
| **E3.1** | `emit_ir_subtree` + wire `screen.py` / `extracted.py`; expand template registry (MVP 7 first, Appendix A incrementally) | S4-A emit |
| **E3.2** | `StyleContext` + golden semantic vs geometric per kind fixture | E3.1 wire |
| **E3.3** | `fidelity_tier` on `WidgetIrNode` + manifest + `stamp_fidelity_tiers` | E3.2 golden harness |
| **E3.5** | `route_by_fidelity_tier` inside semantic branch | E3.3 field |
| **E3.4** | Lint script + CI gate (can land parallel to E3.2 once templates exist) | — |

E3.5 can be implemented immediately after E3.3 with router defaulting all tiers to geometric until manifest promotes kinds.

### Non-negotiables (carry from S1 / Variant B)

- Do **not** collapse `report_only` and `fidelity_tier`.
- Do **not** screen-patch or figmaId-condition semantic emit.
- Semantic kind changes Dart only when **outer gate OFF** AND **tier allows native** AND **template + payload exist**.
- Geometric fallback must preserve pixels; `kind` stays on IR for sync/debug.

### S4 exit criterion

✅ One approved emit architecture (IR-primary recursive), one tier authority (manifest + downgrade), one style path (StyleContext → Jinja), one lint posture (incremental burn-down). Ready for **S5** detailed checklist.

---

## Emit gates — Variant B (locked, do not collapse)

Two **orthogonal** axes composed with **AND** (outer → inner):

| Axis | Question | Scope | Mechanism |
| --- | --- | --- | --- |
| **`report_only`** (E2.5, exists) | Is semantic emit alive **at all**? | Global per run | `SemanticsSettings.report_only` → `_semantic_mvp_emit_enabled(ctx)` |
| **E3.5 tier-router** (new) | Which kinds/nodes are **proven** for native? | Per-node | `ir.fidelity_tier` → emit path selection |

**Do not merge** `report_only` into tier-gate or replace tier-gate with `report_only`.

### Composition (target contract, E3.5)

```text
emit_path = geometric_fallback
if ir.kind in SEMANTIC_MVP_IR_KINDS:
    if _semantic_mvp_emit_enabled(ctx):          # OUTER: report_only master kill-switch
        emit_path = route_by_fidelity_tier(ir)     # INNER: E3.5 per-node router
```

```python
def semantic_native_emit_allowed(ir, ctx) -> bool:
    if not _semantic_mvp_emit_enabled(ctx):
        return False
    return tier_allows_native(ir.fidelity_tier)
```

`_semantic_mvp_emit_enabled(ctx)` **stays** the outer gate (current E2.5 implementation). E3.5 adds the inner `fidelity_tier` router; it does not subsume `report_only`.

### Why keep `report_only` (outer)

1. **E2.5-I invariant:** «same IR with/without classification → identical Dart» needs one switch that disables **all** semantic emit, independent of per-kind tier stamps.
2. **Ops:** production regression → flip one global flag, not audit N tiers.
3. **Debug / strict-fidelity:** compare full-screen semantic vs geometric with global OFF.

### Why add tier-router (inner)

Wave rollout (E5): promote BUTTON to `native_verified` while CHIP stays unverified. All-or-nothing `report_only` alone cannot express per-kind promotion.

### E3.5 is a router, not a bool

`fidelity_tier` (field added in E3.3 — **not on schema yet**) routes to:

| Tier | Emit path |
| --- | --- |
| `native_verified` | Semantic native template emit |
| `native_unverified` | Geometric fallback; **rejected** in strict-fidelity profile |
| `svg_baked` / `png_baked` | Baked asset emit |
| `unsupported` | Geometry / raster fallback |

`report_only=true` short-circuits the **entire** router to geometric path (outer AND fails first).

---

## Rollout defaults

| Setting | Default through E2 / early E3 | When to flip |
| --- | --- | --- |
| `report_only` | `true` (no semantic emit) | When ≥1 kind reaches `native_verified` **and** strict-fidelity corpus is green for that kind (E3 release gate) |
| `fidelity_tier` | Stamped per-node from golden corpus (E3.3) | Per-kind promotion when template golden ≤ ε on kind fixtures |

After `report_only=false`, per-kind authority is **`fidelity_tier`**, not removal of the outer gate — `report_only` remains available as kill-switch.

---

## Config (E3 target)

```yaml
semantics:
  enabled: true
  report_only: true                    # outer master kill-switch (retained)
  llm_gray_zone_annotations: false
  confidence_threshold: 0.8
  grey_zone_min: 0.5
  authoritative_classifier: true
  # E3.3+: fidelity stamped on IR nodes, not a global YAML enum
```

---

## S5 — Implementation checklist (executed)

### E3.1 — IR-primary emit wire

- [x] `generator/layout/widgets/emit/shell.py` — `render_layout_shell`, `render_leaf_body`, `assemble_layout_emit`
- [x] `generator/ir/expression.py` — `emit_screen_body_from_ir`, `IrEmitWalkState`, container/leaf split
- [x] `generator/ir/screen.py` + `extracted.py` wired to IR walk
- [x] `generator/ir/tree.py` — `index_ir_tree`
- [x] `semantic_emit.py` — payload merged into template context
- [x] `tests/test_emit_ir_subtree.py`, `tests/test_extracted_ir_emit.py`
- [x] Fix: `sanitize_screen_ir_llm_drift(strip_llm_semantic_kinds=False)` at emit validate (preserve classifier kinds)

### E3.2 — Style contract

- [x] `generator/ir/style_context.py` — `FigmaStyleContext` / `build_style_context`
- [x] MVP `button_filled.dart.j2` uses `style.*` + Material suppression
- [x] `tests/test_semantic_kind_golden.py`, `tests/support/semantic_golden.py`
- [ ] Remaining 6 MVP templates: incremental style fields (non-blocking)

### E3.3 — `fidelityTier`

- [x] `FidelityTier` enum + `WidgetIrNode.fidelity_tier`
- [x] `tests/fixtures/semantics/fidelity_manifest.yaml`
- [x] `generator/ir/fidelity_manifest.py`, `passes/fidelity.py`, wire in `materialize.py`
- [x] `tests/test_fidelity_stamp.py`
- [ ] CI golden downgrade hook (deferred; manifest + stamp in place)

### E3.4 — CI lint

- [x] `scripts/lint_dart_in_python.py` — blocking on `generator/ir/`, burn-down on `layout/widgets/`
- [x] `tests/fixtures/lint/dart_sniff_baseline.json`
- [x] Wired in `scripts/signoff.ps1` + `signoff.sh`
- [x] `tests/test_dart_in_python_lint.py`

### E3.5 — Inner tier router

- [x] `generator/ir/fidelity_router.py` — `route_by_fidelity_tier`, `semantic_native_emit_allowed`
- [x] Wired in `expression.py` after outer `report_only` gate
- [x] `SemanticsSettings.strict_fidelity`
- [x] `tests/test_fidelity_router.py`

**Release gate unchanged:** `report_only: true` default until product flips after native_verified corpus green.

**Post-review containment (pre-flip):**

- [x] `BAKED_ASSET` path raises `GenerationError` instead of silent geometric fallback (`expression.py`)
- [x] `WidgetIrNode.validate_kind_payload` mutates `self` and returns `self` (constructor payload contract)

---

## Wave checklist (from semantic-core)

### E3.1 — Template infrastructure

- [x] IR walk + MVP 7 templates wired
- [x] Typed Jinja context from IR payload
- [ ] Appendix A kinds beyond MVP 7 (incremental)

### E3.2 — Style contract

- [x] `StyleContext` builder + button template
- [x] Semantic vs geometric harness tests
- [ ] Pixel golden ≤ ε per kind (docker optional)

### E3.3 — `fidelityTier` on IR

- [x] Schema + manifest stamp pass
- [ ] Automated downgrade on golden failure in CI
- [x] Corpus carries tier (`test_fidelity_stamp`)

### E3.4 — CI lint «no Dart in Python»

- [x] Blocking lint in `generator/ir/`
- [x] Burn-down baseline for `layout/widgets/`

### E3.5 — Semantic emit gate (inner router)

- [x] `route_by_fidelity_tier` inside semantic branch
- [x] Variant B AND composition tested
- [x] `strict_fidelity` rejects `native_unverified`

---

## Verification

```bash
poetry run pytest tests/test_emit_ir_subtree.py tests/test_semantics_emit_gate.py \
  tests/test_semantic_kind_golden.py tests/test_fidelity_stamp.py \
  tests/test_fidelity_router.py tests/test_dart_in_python_lint.py -q
poetry run python scripts/lint_dart_in_python.py
```

## Related

- Outer gate today: [epic-2.5-safety.md — Emit rule](epic-2.5-safety.md)
- Classifier seam: [epic-2-classifier.md](epic-2-classifier.md)
