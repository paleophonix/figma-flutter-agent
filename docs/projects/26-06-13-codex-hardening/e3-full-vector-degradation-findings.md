# E3-full — Vector named degradation: S2 findings (prep-only)

> Status: prep-only, S2 findings report — no production changes
> Date: 2026-06-13
> Pipeline: S2 BASE for E3-full (Branch C, P1 fidelity hardening)

---

## 1. E3-lite green proof: absent

- `docs/projects/semantic-core/epic-3-emit.md` (E3.4) describes `scripts/lint_dart_in_python.py` as a
  blocking gate with a burn-down metric for `layout/widgets/` violations against
  `linters/emitter_baseline.txt` (10KB, untracked, live ledger).
- `docs/projects/codex-hardening/codex-hardening.md` lists `lint_dart_in_python green` as the
  E3-lite DoD item and a merge-blocker prerequisite.
- No spec or status doc records an explicit "green"/"done" state for E3-lite.

**Conclusion:** E3-lite is in-flight. Per the agreed rule ("assume NOT green until proven
otherwise"), **E3-full remains prep-only**: no production switch in `svg.py` / `media.py`,
no new blocking lint, no placeholder layer.

---

## 2. The "invent Container" hypothesis from the original E3-full spec is not confirmed

The original C.3 spec assumed:

```text
VECTOR without vector_asset_key/path
  → production silently emits Container(width, height, color)
```

S2 code inspection shows this is **not** what currently happens at the two named functions:

- `generator/layout/widgets/svg.py:211-243 _render_exported_vector`
  - If `vector_asset_key` is missing/unsupported and `image_asset_key` is also missing,
    the function **returns `None`** (line 243). No `Container` is constructed here.

- `generator/layout/widgets/emit/media.py:16-76 render_image_or_vector`
  - If `_render_exported_vector` returns `None` and there is no `layer_blur` /
    `vector_svg_has_filter`, the function **returns `None`** (line 76). No `Container`
    is constructed here either.

The only `Container(width, height, ...color)` emission found near vector code is in
`generator/layout/widgets/playback.py:40-82 _render_native_blur_vector` — but that is a
**blur-vector** fallback (triggered by `layer_blur` / SVG filter), a distinct case from
"bare missing vector asset" described in the spec.

---

## 3. Where the actual silent fallback lives is unresolved

`None` returned from `render_image_or_vector` must become *something* in the emitted Dart —
either an empty/invisible widget or it is filtered out upstream. The most likely candidate
surfaced during the adjacent E1 inventory is:

```text
generator/layout/widgets/emit/dispatch.py:152
  → falls back to SizedBox.shrink() when the extracted widget ref is missing
```

...but this was **not verified** for the specific VECTOR/missing-asset path in this slice —
confirming it would require following the dispatch call graph from
`render_image_or_vector(...) -> None` through to the final emitted widget, which is out of
scope for this prep-only pass (agreed: "do not expand into downstream callsite chase").

**Open question for the next E3-full pass:** confirm whether `dispatch.py:152` (or another
site) is the actual point where a missing VECTOR silently becomes `SizedBox.shrink()` (or
similar) with zero diagnostic — that is the real patch point for
`record_deviation(reason=MISSING_VECTOR_ASSET, severity=DEGRADED)`.

---

### Update (S6, 2026-06-13): confirmed — `dispatch.py:152` was NOT the site

Call-graph trace (see `e3-full-vector-degradation-plan.md` checklist item 2):

```text
shell.py:render_layout_shell (NodeType.VECTOR)
  -> render_image_or_vector(node, ctx, flow) returns None  (media.py:76)
  -> falls through image_asset_leaf, render_simple_controls, all typed branches
  -> render_misc.fallback (emit/containers.py)
       -> child_widgets empty, no svg preference, _render_leaf_surface(node) is None
          (CONTAINER-only, not VECTOR)
       -> emit/containers.py:389 `if node.type == NodeType.VECTOR and not
          node.vector_asset_key:` -> previously silently returned
          `SizedBox.shrink()`
```

This is the confirmed, single patch point. `record_deviation(reason=MISSING_VECTOR_ASSET,
severity=DEGRADED)` is now wired there (see plan checklist item 3); the emitted widget is
unchanged.

---

## 4. F2 infrastructure status: ready, unused

- `debug/provenance.py`: `DeviationReason.MISSING_VECTOR_ASSET`, `DeviationSeverity.DEGRADED`,
  `DeviationRecord`, `ProvenanceRecorder.record_deviation`, serialized into
  `to_payload()["deviations"]` — all implemented and unit-tested
  (`tests/test_deviation_record.py`, 4 passing tests).
- `generator/ir/passes/provenance_record.py::record_deviation(ctx, ...)` — helper exists,
  no-ops if `ctx.provenance is None`.
- **Zero callers** of `record_deviation` with `MISSING_VECTOR_ASSET` anywhere in `generator/`.

No new model work is needed for E3-full; the only remaining work is wiring a real
production callsite once it is identified and E3-lite is green.

---

## 5. No generator-level debug/preview emit policy exists

Checked `generator/ir/context.py:10-36` (`IrEmitPolicy`, `IrEmitContext`): existing flags are
`apply_guards`, `validate`, `semantic_report_only`, `uses_svg`, `strict_fidelity`,
`strict_l10n`, `strict_a11y`. None of these represent a debug/preview "degraded placeholder"
mode (Layer B from the C.3 discussion). Per the agreed decision, **no placeholder layer is
added in this pass** — E3-full's first production slice (once unblocked) should rely on
`DeviationRecord` + debug-report visibility only, not a visual placeholder.

---

## 6. Blockers / next steps for a future E3-full pass

1. Obtain explicit E3-lite green proof (`lint_dart_in_python` blocking and clean against
   `linters/emitter_baseline.txt`).
2. Follow the `render_image_or_vector(...) -> None` call graph to confirm the actual
   downstream point where a missing vector becomes a silent visible/empty widget
   (candidate: `emit/dispatch.py:152`).
3. Only then wire `record_deviation(reason=MISSING_VECTOR_ASSET, severity=DEGRADED)` at the
   confirmed point, per the production policy in the original C.3 spec.
4. Placeholder/diagnostic visual layer (Layer B) remains explicitly out of scope until a
   generator-level debug/preview emit policy is designed — and that design must not depend
   on or duplicate E1's `preview_capture` routing.
