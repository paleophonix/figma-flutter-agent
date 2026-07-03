# IDE integration (spec §19)

CLI-first integration for **VS Code**, **Cursor**, Android Studio, and Claude Code. One entrypoint: the **interactive menu**. A single VS Code task delegates to it (DRY); optional status-bar button via **Task Buttons**.

| File | Purpose |
|------|---------|
| [`.vscode/tasks.json`](../.vscode/tasks.json) | One task: `figma-flutter: menu` → `poetry run figma-flutter -i` |
| [`.vscode/settings.json`](../.vscode/settings.json) | Status bar button (requires Task Buttons extension) |
| [`.vscode/launch.json`](../.vscode/launch.json) | Debug interactive CLI + Flutter `demo_app` |
| [`.vscode/extensions.json`](../.vscode/extensions.json) | Recommended extensions incl. Task Buttons |
| [`AGENTS.md`](../AGENTS.md) | Cursor agent context |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code workflow |

Spec: full IDE extensions are **post-MVP** — [spec-amendments.md](spec-amendments.md) §19.

---

## Prerequisites

1. Agent repo: `poetry install --with dev`
2. Copy `.env.example` → `.env`
3. Flutter app (`../demo_app` or e.g. `E:/@dev/demo_app`)
4. `.ai-figma-flutter.yml` auto-copied on first `run` / `generate`

---

## Quick start

| How | Action |
|-----|--------|
| **Status bar** | Click **`▶ figma-flutter`** (needs [Task Buttons](https://marketplace.visualstudio.com/items?itemName=spencerwmiles.vscode-task-buttons) — Cursor will prompt from `.vscode/extensions.json`) |
| **`Ctrl+Shift+B`** | Same menu (default build task, no extension) |
| **Terminal** | `poetry run figma-flutter -i` |
| **`F5`** | Run and Debug → **figma-flutter — interactive menu** |

Tests and sign-off (not in the menu — run from repo root):

```bash
./scripts/signoff.sh          # or .\scripts\signoff.ps1 on Windows
# or manually:
poetry run pytest -q -m "not live_figma"
poetry run figma-flutter demo-signoff --strict --signoff-gates
```

---

## Interactive menu

Looping menu; default: **select active screen**.

| Menu item | What it does |
|-------------|--------------|
| select active screen | Numbered list from `screens.yaml` → wire `main.dart` |
| run | `flutter run` for the active / picked screen |
| generate | One frame (offline dump or live Figma) |
| batch dump-file | One API call → dumps + `screens.yaml` |
| batch generate | Offline codegen for all screens |
| list screens | View list; optional switch active |
| live-check | Verify Figma token / smoke fetch |
| change Flutter project | Pick another `pubspec.yaml` root |
| quit | Exit |

Header shows project and active screen between iterations.

---

## Run and Debug

| Configuration | Purpose |
|---------------|---------|
| figma-flutter — interactive menu | Debug CLI wizard (`-i`) |
| Flutter: demo_app (chrome) | Launch UI after wiring a screen |
| Flutter: demo_app (select device) | Emulator / physical device |

Adjust `cwd` in `launch.json` if `demo_app` is not at `../demo_app`.

---

## Recommended workflow

```
poetry run figma-flutter -i
  → batch dump-file → batch generate → select active screen → run
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No menu / instant exit | Integrated terminal only; not Output panel |
| Wrong project | Menu → **change Flutter project** |
| `flutter` not found | Install Flutter SDK; restart IDE |
| PowerShell `PS` error | Type only `poetry run figma-flutter -i` |

Further steps: [manual-acceptance.md](projects/production-readiness-2026-05/manual-acceptance.md).
