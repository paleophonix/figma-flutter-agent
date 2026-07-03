# EPIC 6 — Corpus and pixel oracle (S6)

> Status: **W0 implemented** — see [epic-6-w0.md](epic-6-w0.md); corpus growth W1+ pending

Parent program: [semantic-core.md](semantic-core.md) EPIC 6.

## Purpose

Build a **measurable** real-design corpus and pixel oracle so semantic classify/emit acceptance
is objective and CI-blocking — without making the first mergeable slice a hostage of typography,
fonts, or full-corpus pixel noise.

**Invariant:** S6 collects evidence and blocks only a **curated deterministic subset**. It does
not auto-promote fidelity tiers or fail releases solely on glyph raster mismatch before E7.

---

## S6 slice map

| Slice | Scope |
| --- | --- |
| **S6.1** | Real-design corpus foundation (>= 25 screens/fragments) |
| **S6.1.W1** | Real-design W1 semantic corpus (integration-level; S5.W1 stays synthetic unit gate) |
| **S6.2** | Corpus tags: `strict_pixel_blocking` / `advisory_pixel` / `semantic_only` |
| **S6.3** | Visual oracle metrics: geometry, non-text pixel, text-region pixel |
| **S6.4** | Strict geometry gate (blocking) |
| **S6.5** | Strict pixel blocking subset (8–12 screens) |
| **S6.6** | Advisory full corpus report (non-blocking) |
| **S6.7** | Semantic no-op oracle (post-E3 emit world) |
| **S6.8** | Full-tree semantic FP audit on real-design corpus |
| **S6.9** | Golden/capture determinism report |
| **S6.10** | Fidelity promotion **candidates** (dry-run only; no manifest mutation in CI) |

---

## Corpus tiers (S6.1 / S6.2)

S6 maintains a real-design corpus of **at least 25** screens/fragments.

Only a curated deterministic subset is `strict_pixel_blocking`. The rest is `advisory_pixel`.

| Tier | Count (initial) | CI behavior |
| --- | ---: | --- |
| **Total real-design corpus** | >= 25 | All fixtures offline; no live Figma API in gate |
| **`strict_pixel_blocking`** | 8–12 | Release-blocking gates |
| **`advisory_pixel`** | remainder | Report-only; backlog / failure capsules |
| **`semantic_only`** | as tagged | Classify gates only; no pixel block |

### Blocking subset admission criteria

A fixture enters `strict_pixel_blocking` only when:

```text
stable Figma reference
deterministic Flutter render
no known text-metric instability
no async/image/font race
golden capture warm/repeatable
layout does not depend on live data
```

### Blocking gates (`strict_pixel_blocking`)

```text
non_text_pixel_diff <= threshold
geometry_iou >= threshold
text_bounds_delta <= tolerance
no missing nodes
no unexpected semantic nodes
no conservation violations
```

### Advisory gates

```text
report only
no release block
creates backlog / failure capsule
```

---

## Text handling in strict_pixel (pre-E7)

Until E7 typography is implemented, strict pixel gates **separate structural pixels from text
glyph pixels**.

| Metric | Role before E7 |
| --- | --- |
| `non_text_pixel_diff` | **Blocking** (strict_pixel_blocking subset) |
| `geometry_iou` | **Blocking** |
| `text_bounds_delta` | **Blocking** (layout/text rect shift beyond tolerance) |
| `text_region_pixel_diff` | **Advisory** |
| Glyph antialiasing / font fallback / line-height raster mismatch | **Advisory** |

A screen must **not** fail `strict_pixel_blocking` solely because glyph rasterization differs
inside known text regions before E7.

Oracle channel split (S6.3):

```text
strict_geometry     → blocking
strict_pixel        → blocking subset only (structural channel)
strict_text         → advisory until E7
```

---

## E6.8 — Semantic no-op oracle (updated for post-E3 emit)

Historical wording (“before E3”) reflected build order. Emit exists today; the gate is:

**Classification must not change emitted Dart or pixels unless the node is authorized by the
fidelity manifest.**

Required no-op modes:

1. `semantic_report_only=true`
2. `fidelityTier=native_unverified`
3. `fidelityTier=styled_primitive` when the expected path is geometric/styled fallback
4. Classifier accepted a kind but manifest does not allow `native_verified`

```text
emit(auto_ir) == emit(classified_ir) when report_only=true

native template emit only when fidelityTier=native_verified
```

Allowed diffs: `.debug/semantics/*.json`, IR metadata snapshots only.

---

## E6.10 — Fidelity promotion ownership (E6 vs E4.5)

### E6 signoff owns

```text
golden/diff execution
visual QA reports
strict/advisory corpus status
verification result artifact
fidelity_promotion_candidates.json (recommendations)
```

### E4.5 manifest owns

```text
fidelity manifest schema
tier semantics (native_verified / native_unverified / styled_primitive / baked policy)
```

### Manual promote bridge (human PR)

Signoff **must not** edit `fidelity_manifest.yaml`.

```text
E6 signoff produces verification evidence
  → human reviews
  → figma-flutter fidelity promote --dry-run
  → optional --write-patch
  → PR + review + merge
```

```bash
figma-flutter fidelity promote --kind button_outlined --fixture btn-outlined --dry-run
figma-flutter fidelity promote --kind button_outlined --fixture btn-outlined --write-patch
```

| Rule | Gate |
| --- | --- |
| Signoff may **recommend** promotion | allowed |
| Signoff **mutates** manifest | forbidden |
| `--dry-run` in CI | mandatory |
| `--write-patch` | local/manual only |

Live `generate` only **reads** manifest; stale/missing entry → `native_unverified` or policy fallback.

---

## S6.1.W1 — Real-design W1 corpus

Extends [epic-5-w1.md](epic-5-w1.md) synthetic W1 gate with real Figma dumps.

| Layer | Role |
| --- | --- |
| **S5.W1** | Synthetic deterministic **unit** semantic classifier gate |
| **S6.1.W1** | Real-design **integration** oracle for W1 kinds |

Per-fixture tags (required): `semantic_only` | `advisory_pixel` | `strict_pixel_blocking`

Initial acceptance:

```text
real_design_w1_cases >= 10
real_design_w1_negative_traps >= 5
unexpected_semantic_nodes == 0
blocker_negative_false_positives == 0
```

Synthetic S5.W1 precision/recall gates remain on programmatic corpus; S6.1.W1 adds real-design
fixtures under E6 manifest (not `tests/fixtures/layouts/semantics/w1.real_design_cases` backlog alone).

---

## Mapping to EPIC 6 table (semantic-core)

| E6 # | S6 owner slice |
| --- | --- |
| E6.1 | S6.1, S6.1.W1, S6.2 |
| E6.2 | S6.5 blocking + S6.6 advisory |
| E6.3 | S6.6, S6.9 artifacts |
| E6.4 | S6.3–S6.5 (`strict_pixel` on blocking subset; `layout_pixel` / `semantic_runtime` advisory) |
| E6.5 | S6.4+ (metamorphic laws on blocking subset first) |
| E6.6 | Coverage matrix expansion beyond W1 rows |
| E6.7 | Affine adversarial fixtures; baked tier or native proof |
| E6.8 | S6.7 |
| E6.9 | S6.8 + semantic report aggregates |
| E6.10 | S6.10 (candidates only; E4.5 promote is manual) |

---

## Epic DoD (refined)

1. **>= 25** real-design corpus fixtures with goldens; **8–12** in `strict_pixel_blocking`
2. Blocking CI: geometry + non-text pixel + semantic gates on blocking subset
3. Advisory corpus report on every signoff (full >= 25)
4. Semantic no-op oracle per E6.8 (report_only + unverified/styled paths)
5. `fidelity_promotion_candidates.json` artifact; **no** CI manifest mutation
6. Coverage matrix is the explicit Figma support contract

---

## Non-goals (first S6 mergeable slice)

- All >= 25 fixtures as `strict_pixel_blocking` on day one
- CI auto-promote to `native_verified`
- Blocking on glyph/text raster diff before E7
- Live Figma API in corpus gate runs
- Replacing S5.W1 synthetic unit gate with real-design-only corpus

---

## Short decisions (team summary)

```text
Corpus-subset:
  >=25 total real-design corpus
  8–12 strict_pixel_blocking
  rest advisory

E6.8:
  no-op post-E3:
  report_only=true + native_unverified must not affect emit/pixels

E6.10 owner:
  E6 owns signoff evidence
  E4.5 owns manifest
  promote is manual dry-run/patch bridge
  CI must not mutate manifest

Real-design W1:
  S6.1.W1 under E6, not S5
  S5 synthetic stays unit gate

Text in strict_pixel:
  non_text_pixel_diff blocks
  text_region_pixel_diff advisory until E7
  text_bounds_delta may block
```
