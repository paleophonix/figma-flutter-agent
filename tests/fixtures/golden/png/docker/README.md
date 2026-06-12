# Layout smoke golden baselines (NOT Figma screenshots)

PNG files here are **offline regression baselines** for `tests/fixtures/screens.yaml`.

They are **not** copies of your Figma `sign_in` frame or `demo_app` output.

## What they actually capture

- Synthetic **minimal** clean-tree JSON under `tests/fixtures/layouts/`
- Deterministic codegen (no LLM), rendered in the Flutter test harness
- Stub SVG icons (placeholder copied per `vectorAssetKey`)
- Widgets are placed in the **lower half** of a 414×896 canvas (large empty top area is expected)

Use them only to detect **unintended layout/codegen drift** in CI (AC-1 pixel compare).

## What to use for real UI

| Goal | Where |
|------|--------|
| Real screen from Figma | `poetry run figma-flutter generate --project-dir ../demo_app` |
| Combat Flutter vs Figma PNG | `logs/renders/{timestamp}-{run_id}/` after generate with visual refine |
| Figma reference in project | `demo_app/.figma-flutter/reference/{feature}_figma.png` |

## Update baselines

```powershell
poetry run python scripts/generate_fixture_goldens.py --update-goldens --golden-runtime docker
```

Commit updated PNGs only when layout fixture or deterministic codegen changes are intentional.
