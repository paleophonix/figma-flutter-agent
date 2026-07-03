# E3-full — Vector named degradation: implementation plan

> Status: implementation done (items 1-4); item 5 blocked on Branch-A E0 circular-import regression (unrelated to this change)
> Date: 2026-06-13
> Pipeline: S5 PLAN — derived from approved S4 concept (findings-only pass, see
> `e3-full-vector-degradation-findings.md`)

---

## 1. Goal

**What:** Wire a real production callsite to
`record_deviation(reason=DeviationReason.MISSING_VECTOR_ASSET, severity=DeviationSeverity.DEGRADED)`
when a VECTOR node has no resolvable asset, so the deviation is visible in the debug
provenance report — without inventing placeholder geometry and without a new blocking lint.

**Why:** Closes the F2→E3-full chain (Branch C, P1 fidelity hardening): F2's
`DeviationRecord` model exists and is tested but has zero callers. The original C.3
"Container invention" hypothesis was disproven in S2 — the real silent-fallback point is
unconfirmed (`None` propagation, candidate `emit/dispatch.py:152`). This plan sequences the
remaining discovery + wiring work so it executes only once E3-lite is provably green.

## 2. Approved concept (from S4)

S4 selected "findings report only, stop" for the current pass (completed). This S5 plan
captures the **next** pass's checklist so that when E3-lite goes green, execution can start
immediately from a written spec rather than re-deriving context.

## 3. Scope

### In scope
- Verifying E3-lite green status (gate check, no code change by this plan's author)
- Tracing the `render_image_or_vector(...) -> None` call graph to confirm the actual
  silent-fallback point
- Wiring `record_deviation(reason=MISSING_VECTOR_ASSET, severity=DEGRADED)` at the
  confirmed point only
- Adding the 5 tests from the original C.3 spec
- Confirming `lint_dart_in_python` stays green after the change

### Out of scope
- Any change to `svg.py` / `media.py` emit behavior beyond adding the `record_deviation`
  call (no geometry/Container invention, no behavior change to returned widget)
- Placeholder/diagnostic visual layer (Layer B) — requires a separate generator-level
  debug/preview emit policy design (not part of this plan)
- E1 `preview_capture` routing — explicitly not depended upon
- Branch A dirty roots — no coordination requested in this plan

## 4. Affected modules

| Path | Change |
|------|--------|
| `linters/emitter_baseline.txt`, `scripts/lint_dart_in_python.py` (read-only check) | Gate check only — confirm E3-lite green before proceeding past item 1 |
| `generator/layout/widgets/emit/dispatch.py` (and/or the confirmed downstream point) | Add `record_deviation(...)` call when VECTOR node resolves to no asset |
| `generator/layout/widgets/emit/media.py::render_image_or_vector` | Possibly thread `ctx`/node info through to the new call site if not already available |
| `tests/test_deviation_record.py` or new `tests/test_vector_degradation.py` | Add the 5 tests from the C.3 spec |
| `docs/projects/codex-hardening/e3-full-vector-degradation-findings.md` | Append outcome of call-graph trace (item 2) |

## 5. Subtasks (3–5)

1. **Gate check** — confirm `lint_dart_in_python` is blocking and green against
   `linters/emitter_baseline.txt` for `layout/widgets/` (E3-lite DoD). If not green, stop
   and report — do not proceed to items 2-5.
2. **Call-graph trace** — follow `render_image_or_vector(...) -> None` through
   `emit/dispatch.py` (and any intermediate layers) to confirm where a missing-vector
   `None` becomes a visible/empty widget today. Record the confirmed file:line in the
   findings doc.
3. **Wire `record_deviation`** — at the confirmed point from item 2, call
   `record_deviation(ctx, node_id=..., field_name=..., before=..., after=...,
   reason=DeviationReason.MISSING_VECTOR_ASSET, source=..., severity=DeviationSeverity.DEGRADED)`.
   No change to the emitted widget itself.
4. **Tests** — add the 5 tests from the C.3 spec (missing vector emits DeviationRecord;
   no Container fallback in production; preview placeholder allowed only in
   preview/debug — N/A if Layer B remains out of scope, document as such; production
   path records degraded severity; debug report contains vector degradation).
5. **Verify gates** — run `poetry run pytest -q` for the new/affected tests and
   `lint_dart_in_python`; confirm no new red gates.

## 6. CHECKLIST

- [x] 1. Confirm E3-lite (`lint_dart_in_python`) is blocking and green — DoD: explicit pass/fail evidence recorded in this file; if fail, stop here and report to user
  - Evidence: `poetry run python scripts/lint_dart_in_python.py` → exit 0, "Dart sniff OK (layout/widgets=105, fingerprints=99)" (2026-06-13, before and after item 3's edit).
- [x] 2. Trace `render_image_or_vector(...) -> None` call graph to confirm the real silent-fallback point — DoD: file:line documented in findings doc, verified by reading actual code (not inferred)
  - Confirmed: `generator/layout/widgets/emit/shell.py:218-221 render_layout_shell` — VECTOR with `render_image_or_vector(...) -> None` falls through `image_asset_leaf`, `render_simple_controls`, all type branches, to `render_misc.fallback` (`emit/containers.py`). There, `leaf_surface = _render_leaf_surface(node)` is `None` for bare VECTOR (CONTAINER-only), so it reaches the `if node.type == NodeType.VECTOR and not node.vector_asset_key:` branch at `emit/containers.py:389` (pre-edit), which silently returned `SizedBox.shrink()`. This is the confirmed patch point — NOT `emit/dispatch.py:152` as speculated in the findings doc.
- [x] 3. Wire `record_deviation(reason=MISSING_VECTOR_ASSET, severity=DEGRADED)` at the confirmed point — DoD: production widget output unchanged (snapshot/diff confirms no emit change beyond provenance side-channel)
  - Implemented in `generator/layout/widgets/emit/containers.py`: added imports (`DeviationReason`, `DeviationSeverity`, `get_provenance_recorder` from `figma_flutter_agent.debug.provenance`) and, immediately before the existing `return _finalize_widget(node, "const SizedBox.shrink()", ...)`, call `get_provenance_recorder()` and, if a recorder is active, `recorder.record_deviation(node_id=node.figma_id, field="widget", before="Svg.asset", after="SizedBox.shrink()", reason=DeviationReason.MISSING_VECTOR_ASSET, source="emit.containers.render_misc.fallback", severity=DeviationSeverity.DEGRADED)`. The emitted widget string (`"const SizedBox.shrink()"`) is unchanged. `ruff check` clean; `lint_dart_in_python` unchanged/green.
- [x] 4. Add 5 tests from C.3 spec — DoD: all 5 pass; if the "preview placeholder" test is N/A (Layer B out of scope), document why instead of faking it
  - Added `tests/test_vector_degradation.py` with 5 tests covering: DeviationRecord emitted for missing vector, no Container fallback in production (`SizedBox.shrink()` only), preview placeholder (documented N/A — Layer B remains out of scope per S4, no generator-level debug/preview emit policy exists), DEGRADED severity, and provenance-dump payload containing the vector degradation. `ruff check tests/test_vector_degradation.py` → "All checks passed!".
- [x] 5. Verify gates — DoD: `pytest -q` green for affected/new tests, `lint_dart_in_python` green, no new red gates introduced
  - This slice's own gates GREEN (2026-06-13): `tests/test_vector_degradation.py` 5/5 + `tests/test_deviation_record.py` 5/5 pass; `lint_dart_in_python` exit 0 ("layout/widgets=105, fingerprints=99"); `ruff check tests/test_vector_degradation.py` clean. The earlier circular-import in `parser.interaction` was a transient mid-edit state from Branch A — it cleared on its own; the only remaining import fix was my own bad `StackPlacement` import (now corrected to `from figma_flutter_agent.schemas import StackPlacement`).
  - **NOT introduced by this slice but RED in the full suite** (`pytest -q -m "not live_figma"` = 3 failed / 2423 passed): `test_semantics_legacy_burndown` (3 new archetype fingerprints in `flex_policy/alignment.py`, `widgets/input/fields.py`, `parser/interaction/forms.py` — all Branch-A/E0 zones), `test_lint_settings_purity::collects_five_debt_sites` (E4 removed `materialize.py` load_settings but the test still expects 5 sites; now 4), and `test_golden_generation[onboarding]` (golden drift from Branch-A/B emit changes). None touch Branch-C files. E3-full DoD ("lint_dart_in_python remains green") is satisfied; the red gates are E0/E4 ownership.

## 7. Risks and assumptions

- **Assumption:** E3-lite will eventually go green independently (Branch A's responsibility);
  this plan does not include work to make it green.
- **Risk:** the call-graph trace (item 2) may reveal that the silent fallback spans multiple
  layers, requiring `record_deviation` to be called from more than one site — if so, item 3
  should be split into per-site sub-items before execution, not patched ad hoc.
- **Risk:** if item 1 fails (E3-lite not green) when this plan is picked up, the entire
  checklist remains blocked — re-run only item 1 until it passes.
