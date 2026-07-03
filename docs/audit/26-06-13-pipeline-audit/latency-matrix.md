# Latency matrix — preview vs oracle vs sketch

**Method:** code-path tracing + documented timeouts. No full `flutter test` benchmark run in this review (product constraint: avoid 2000+ pytest / long capture loops).

## Path comparison

| Entry point | Backend | Typical cost driver | Diff / oracle? | Evidence |
| --- | --- | --- | --- | --- |
| `figma-flutter preview-capture --layout-json` | Playwright/Chrome HTML sketch | seconds | no | [`preview_capture/capture.py`](../../src/figma_flutter_agent/preview_capture/capture.py), [`tests/test_preview_capture.py`](../../tests/test_preview_capture.py) |
| `capture_with_mode(PREVIEW)` router | browser only | seconds | no | [`preview_capture/router.py`](../../src/figma_flutter_agent/preview_capture/router.py) |
| Wizard View → **preview** | `flutter test` warm sandbox | minutes (first compile) | no diff | [`view_renders.py:run_view_preview_capture`](../../src/figma_flutter_agent/dev/view_renders.py) — `backend: flutter_test` |
| Wizard View → **oracle** | same `_capture_flutter_render_png()` | minutes | no diff in view path | [`view_renders.py:run_view_oracle_capture`](../../src/figma_flutter_agent/dev/view_renders.py) |
| Post-generate `debug_capture` preview mode | warm sandbox first, then filename only | minutes | diff skipped | [`debug/capture.py:167-189`](../../src/figma_flutter_agent/debug/capture.py) |
| Post-generate oracle mode | warm sandbox + pixel diff + heatmap | minutes+ | yes | [`debug/capture.py:191-217`](../../src/figma_flutter_agent/debug/capture.py) |
| Wizard View → **renders** (combat) | warm sandbox + Figma diff | up to 20 min timeout | yes | [`view_renders.py:40-41`](../../src/figma_flutter_agent/dev/view_renders.py) |
| `generate` default pipeline | full LLM + emit + **visual refine loop** | minutes–tens of min | optional pixel loop | `llm_visual_refine: true` default |
| Wizard launch/run | `run_pipeline` + cached IR path | same as generate minus fetch | refine if enabled | [`dev/wizard/sync.py`](../../src/figma_flutter_agent/dev/wizard/sync.py) |

## Decision tree (product boundary)

```text
User wants quick visual feedback
├─ Has processed layout JSON only?
│  └─ YES → figma-flutter preview-capture (browser sketch, FAST)
└─ Needs Flutter chrome parity?
   ├─ Wizard View → "preview"  → flutter test (SLOW) — mislabeled fast path
   ├─ Wizard View → "oracle"   → flutter test (SLOW) — same capture fn
   ├─ Wizard View → "renders"  → flutter test + diff (SLOW, explicit)
   └─ generate / launch        → full pipeline + visual refine (SLOWEST default)

User wants fidelity gate
├─ CI signoff → corpus-oracle / fixture-geometry (explicit, blocking)
└─ Local dev  → default_capture_mode oracle + debug_capture
```

## Timeout evidence

- Wizard warm capture: **1200s (20 min)** minimum extended timeout — [`view_renders.py:40-41`](../../src/figma_flutter_agent/dev/view_renders.py)
- `apply_interactive_preview_profile`: **no-op** — does not disable `llm_visual_refine` — [`config/profiles.py:40-47`](../../src/figma_flutter_agent/config/profiles.py)

## Warm vs cold sandbox (qualitative)

| State | `flutter test` capture |
| --- | --- |
| Cold (first wizard view on machine) | pub get + compile — dominates latency |
| Warm (`dev/warm_capture.py` session cache) | faster, still seconds–minutes vs browser sketch |

## Product implication

**Only two truly fast paths exist today:**

1. Browser sketch CLI (`preview-capture`)
2. `flutter run` after code is already compiled (wizard launch — not a PNG preview)

Everything labeled **preview** in wizard/debug still pays **flutter test** cost before the mode name affects output.
