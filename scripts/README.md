# Scripts

Shell helpers and maintainer utilities for **figma-flutter-agent**. Run from repo root unless noted.

## Release gates

| Script | Platform | Purpose |
|--------|----------|---------|
| [`signoff.sh`](signoff.sh) | Linux/macOS | ruff → mypy → `demo-signoff --strict --signoff-gates` → pytest |
| [`signoff.ps1`](signoff.ps1) | Windows | Same as `signoff.sh` |
| [`visual-qa-signoff.sh`](visual-qa-signoff.sh) | Linux/macOS | Visual QA pytest subset + `demo-signoff --strict --signoff-gates --visual-qa` |
| [`visual-qa-signoff.ps1`](visual-qa-signoff.ps1) | Windows | Same as `visual-qa-signoff.sh` |

**Requires:** Poetry, and **Flutter/dart on `PATH`** for `demo-signoff --signoff-gates` (dart analyze in spec23).

```bash
./scripts/signoff.sh
./scripts/visual-qa-signoff.sh   # optional, after signoff or standalone
```

```powershell
.\scripts\signoff.ps1
.\scripts\visual-qa-signoff.ps1
```

CI runs the same gates in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): job `lint` (ruff, mypy), job `signoff` (`signoff.sh` + `demo-signoff --visual-qa`).

## Manual E2E helper

Automates offline sign-off + live Figma fetch + production generate + `flutter analyze`. Runtime smoke (`flutter run`) is still manual.

| Script | Usage |
|--------|--------|
| [`e2e-manual.sh`](e2e-manual.sh) | `./scripts/e2e-manual.sh "<FIGMA_URL>" ../demo_app` |
| [`e2e-manual.ps1`](e2e-manual.ps1) | `.\scripts\e2e-manual.ps1 -FigmaUrl "..." -ProjectDir E:\@dev\demo_app` |

Record results in [tests/README.md — Manual E2E acceptance](../tests/README.md#manual-e2e-acceptance).

## Maintainer utilities

| Script | Purpose |
|--------|---------|
| [`regen-layout-from-dump.py`](regen-layout-from-dump.py) | Regenerate `lib/generated/<feature>_layout.dart` from a cached `.figma_debug/raw/<feature>_layout.json` (no Figma API) |
| [`generate-font-registry.py`](generate-font-registry.py) | Regenerate `data/font-registry.v1.yaml` after font mapping changes |

```bash
poetry run python scripts/regen-layout-from-dump.py \
  --dump ../demo_app/.figma_debug/raw/sign_in_layout.json \
  --project-dir ../demo_app \
  --feature sign_in

poetry run python scripts/generate-font-registry.py
```

See [src/figma_flutter_agent/fonts/README.md](../src/figma_flutter_agent/fonts/README.md) for font registry context.
