# Visual QA profile (optional)

Offline and live workflows for reference PNG export, golden test scaffolds, and dark theme generation.

## Config

[`.ai-figma-flutter-visual-qa.yml`](../../../.ai-figma-flutter-visual-qa.yml):

| Setting | Effect |
|---------|--------|
| `dark_mode.enabled: true` | Emits `AppTheme.dark()` in `app_theme.dart` + `ThemeMode` in `main.dart` |
| `validation.export_figma_reference: true` | Saves `.figma-flutter/reference/{feature}_figma.png` (requires live Figma fetch) |
| `validation.generate_golden_test: true` | Emits `test/golden/{feature}_screen_test.dart` |

## Generate with visual QA

```bash
poetry run figma-flutter generate \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir ../demo_app \
  --config .ai-figma-flutter-visual-qa.yml
```

Production gates still apply (non-dry-run default). For soft gates add `--allow-dev-profile`.

## Offline CI / local sign-off

```bash
# Linux/macOS
./scripts/visual-qa-signoff.sh

# Windows
.\scripts\visual-qa-signoff.ps1
```

Runs:

1. `pytest tests/test_golden_generation.py` — planner output vs committed goldens
2. `demo-signoff --strict --config .ai-figma-flutter-visual-qa.yml` — fixture §23 with visual YAML loaded

Refresh goldens after intentional planner changes:

```bash
UPDATE_GOLDEN=1 poetry run pytest tests/test_golden_generation.py -q
```

## Flutter golden tests (human)

After generate into `demo_app`:

```bash
cd ../demo_app
flutter test test/golden --update-goldens   # first run / design change
flutter test test/golden                    # regression
```

Compare reference PNG manually or extend with `golden_toolkit` / custom diff tooling (post-MVP automation).

## Limitations

- Reference export requires network + `FIGMA_ACCESS_TOKEN`
- Golden tests compare rendered Flutter output, not Figma pixels directly (spec §21 partial)
- See [limitations.md](../../limitations.md) for `layer_first` path scope
