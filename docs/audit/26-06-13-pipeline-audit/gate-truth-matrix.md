# Gate truth matrix — what green actually means

## Matrix

| Gate | What it proves | What it does **not** prove | Vacuous / skip risk |
| --- | --- | --- | --- |
| **demo-signoff** (5 JSON fixtures) | spec23 production readiness on carousel/tabs/nav/grid samples | Real customer screens; text-hint misclassification; reconcile pass regressions | Fixtures are curated API-shaped trees, not dirty Figma exports |
| **fixture-ir-validate** | IR guards on fixture manifest | Deterministic emit-only paths without LLM; emit archetype overlap | Passes if fixtures omit failure modes |
| **fidelity validate** | Fidelity engine config consistency | Pixel truth on new screens | Config-level, not corpus-wide |
| **corpus-oracle blocking** | Pixel + geometry IoU on `screens.yaml` manifest | Screens not in manifest; classifier precision | `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1`; skipped blocking screens |
| **corpus-oracle advisory** | Same metrics, non-blocking tier | — | Green while blocking tier fails if only advisory run |
| **semantics corpus-gate** | W1 precision/recall on classification fixtures | Per-run mislabel on new tree; parser `interaction/*` text hints | Offline corpus ≠ live parse path |
| **fixture-geometry-check** | Placement IoU vs Figma keys | Vertical text offset in inputs; checkbox→TextField | `FIGMA_GEOMETRY_SIGNOFF=0` disables entire step |
| **pytest corpus** | Unit contracts on known strings/layouts | Generalization to unseen Figma | Planned-dict string tests = regression anchors |
| **ruff/mypy/lint scripts** | Style, regex-dart-surgery burndown | Runtime layout truth | Burndown allows known debt |
| **runtime_fail_renderflex_overflow** | RenderFlex in golden logs | Pre-emit overflow; IR graph issues | Only when profile enables |
| **Per-run ai_ux report** | Advisory UX/a11y hints | **Non-blocking** — pipeline succeeds with warnings | Touch target warnings don't fail generate |
| **Per-run semantics.json** | Classification trail | Blocking only if `strict_fidelity` (production) | Default `report_only: true` on semantics settings |
| **diff-triada (audit)** | Normalize→emit node counts + soft geometry | LLM IR path; pixel | Skips raw Figma fixtures |

## Corpus overlap gaps

| Set | Members | Overlap |
| --- | --- | --- |
| demo-signoff | `figma_*_sample.json` (5) | **Disjoint** from audit corpus |
| audit corpus | sign_up, reminders, music_v2, bounded_order_card, synthetic rows… | Structural patterns |
| screens.yaml oracle | manifest-driven | Partial overlap with audit corpus |
| limbo wizard | login_version_1, etc. | Live Figma — **not** in demo-signoff |

**Gap:** Passing demo-signoff + corpus-oracle on manifest does not cover wizard's active screen unless it is in `screens.yaml`.

## ≥3 documented "green but risky" splits

1. **Wizard preview green, product slow:** PNG capture succeeds via `flutter test` while user believed preview = fast sketch ([`latency-matrix.md`](latency-matrix.md)).
2. **Generate success + ai_ux warnings:** Pipeline exits 0 with touch-target / nesting advisories ([`sandbox/limbo/.debug/reports/login_version_1_ai_ux.json`](../../sandbox/limbo/.debug/reports/login_version_1_ai_ux.json)).
3. **Semantics report_only vs parse-time NodeType:** IR semantic pass is report-only by default, but `parser/interaction/*` still assigns INPUT/BUTTON from text before emit — corpus-gate does not gate that path.
4. **Oracle allow-skip:** CI can be green with skipped blocking screens when `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1`.
5. **Prompt-only systemic rules (52 total, ~1 mapped prompt-only in sample):** LLM can violate LayoutBuilder ban until dart analyze / manual review — no IR fail-closed.

## Golden update discipline

[`scripts/generate_fixture_goldens.py`](../../scripts/generate_fixture_goldens.py):

- Default: **check** mode (compare to baseline)
- Writes require `--update-goldens`
- Docker writes require `--golden-runtime docker`

**Good:** explicit intent for baseline mutation.  
**Gap:** No automated regression explanation artifact beyond compare failure — human must interpret diff.
