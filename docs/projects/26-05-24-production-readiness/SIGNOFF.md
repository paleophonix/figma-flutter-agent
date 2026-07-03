# Production sign-off status (2026-05)

Review backlog: [production-readiness-review-checklist.md](../code-review-2026-05/production-readiness-review-checklist.md).  
Hard production gaps: [hard-production-checklist.md](../code-review-2026-05/hard-production-checklist.md).

| Gate | Status | Command / artifact |
|------|--------|-------------------|
| Unit + integration tests | Automated | `poetry run pytest -q` |
| Ruff + mypy | Automated | CI `test` job |
| Spec §23 (fixtures) | Automated | `figma-flutter demo-signoff --strict` |
| Dart analyze (fixture) | Automated when Dart installed | `pytest tests/test_demo_signoff.py` |
| Custom-code preservation | Automated when Dart installed | `test_demo_custom_code_preserved_on_regen` |
| Live Figma fetch | Optional CI / local | `figma-flutter live-check --dump` + `pytest -m live_figma` |
| Visual QA (golden + dark profile) | Automated (CI acceptance) | `scripts/visual-qa-signoff.sh` |
| Prototype transitions | Automated (fixtures) | `tests/test_transitions.py`, `tests/test_prototype.py` |
| Real frame + demo_app | **Manual** | [manual-acceptance.md](manual-acceptance.md) §2–8 |

## Recommended local sequence

```bash
poetry install --with dev
poetry run figma-flutter demo-signoff --strict
poetry run pytest tests/test_demo_signoff.py -q
# Optional with .env FIGMA_* smoke vars:
poetry run figma-flutter live-check --dump
```

## Live demo (human)

1. `flutter create demo_app` and configure `.env` + `.ai-figma-flutter.yml`
2. `figma-flutter live-check --dump` — confirm PAT and frame id
3. `figma-flutter generate --figma-url ... --project-dir ../demo_app`
4. `cd ../demo_app && flutter analyze && flutter run -d chrome`

Mark the manual table in [manual-acceptance.md](manual-acceptance.md) when complete.
