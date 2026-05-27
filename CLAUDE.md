# Claude Code — figma-flutter-agent workflow

This repo converts a **Figma frame URL** into Flutter files inside a target app. Use terminal commands; there is no Figma sidebar plugin.

## Setup (once)

```bash
poetry install --with dev
cp .env.example .env
# Edit .env: FIGMA_ACCESS_TOKEN, LLM_PROVIDER, LLM_GENERATE_MODEL, optional LLM_REPAIR_MODEL / LLM_REFINE_MODEL, optional LLM API keys
flutter create ../demo_app   # outside this repo
```

`.ai-figma-flutter.yml` lives in the **figma-flutter-agent repo root** (copy from `.ai-figma-flutter.yml.example`). LLM provider and model live in `.env` only — not in YAML.

## Interactive menu (day-to-day)

```bash
poetry run figma-flutter -i    # or F5 → "figma-flutter — interactive menu"
```

Looping wizard: select active screen, run, generate, batch dump/generate, list screens, live-check, change project. See [README — VS Code / Cursor](README.md#vs-code--cursor).

## Standard workflow

1. **Verify credentials**

```bash
poetry run figma-flutter live-check --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" --dump --project-dir ../demo_app
```

2. **Dry-run** (no writes)

```bash
poetry run figma-flutter generate \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir ../demo_app \
  --dry-run
```

3. **Generate** (production gates on by default)

```bash
poetry run figma-flutter generate \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir ../demo_app
```

**Default codegen path is deterministic** (rule-based layout, no LLM). Set `generation.use_deterministic_screen: false` in the agent repo `.ai-figma-flutter.yml` for LLM screen bodies.

Dev-only soft gates: add `--allow-dev-profile`.

4. **Validate Flutter app**

```bash
cd ../demo_app
dart format .
flutter analyze
flutter run -d chrome
```

5. **Offline sign-off** (agent repo)

```bash
cd ../figma-flutter-agent
./scripts/signoff.sh          # or .\scripts\signoff.ps1 on Windows
```

Equivalent manual steps:

```bash
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run pytest -q -m "not live_figma"
./scripts/visual-qa-signoff.sh   # optional: golden tests + demo-signoff --visual-qa
```

Optional visual QA (dark theme, reference PNG, golden scaffold): enable flags in the agent repo `.ai-figma-flutter.yml`, or:

```bash
poetry run figma-flutter demo-signoff --strict --signoff-gates --visual-qa
```

## Editing generated code

Only change logic inside:

```dart
// <custom-code>
// </custom-code>
```

Regeneration merges custom zones and may overwrite edits outside them. With `strict_preservation`, the agent refuses to write if orphan edits are detected.

## When changing this Python project

- Read [README — Spec interpretation](README.md#spec-interpretation) and [Notes & limitations](README.md#notes--limitations) for scope
- Run ruff + mypy + pytest before proposing completion
- See [AGENTS.md](AGENTS.md) for architecture and DI/logging rules
- IDE: [README — VS Code / Cursor](README.md#vs-code--cursor)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `FIGMA_ACCESS_TOKEN` | Figma REST API |
| `FIGMA_FLUTTER_PROJECT_DIR` | Default Flutter project when `--project-dir` is omitted (env only) |
| `FIGMA_SMOKE_FILE_KEY` / `FIGMA_SMOKE_NODE_ID` | Optional live-check / `pytest -m live_figma` |
| `LLM_PROVIDER` | `anthropic` \| `openai` \| `openrouter` \| `google` |
| `LLM_GENERATE_MODEL` | Primary codegen model override (env only; not in YAML) |
| `LLM_REPAIR_MODEL` | Analyze repair model override; falls back to `LLM_GENERATE_MODEL` |
| `LLM_REFINE_MODEL` | Visual refine model override; falls back to `LLM_GENERATE_MODEL` |
| `LLM_REQUIRE_STRICT_JSON_SCHEMA` | Prefer strict JSON schema when provider supports it |

Never print or commit API keys.
