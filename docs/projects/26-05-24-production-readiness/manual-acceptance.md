# Manual E2E acceptance (production sign-off)

**Owner:** _______________  
**Date:** _______________  
**Figma frame URL:** _______________ (no secrets in this file)  
**Flutter project path:** _______________  
**Agent version / git SHA:** _______________

This checklist closes **P0-4** in [production-backlog.md](../code-review-2026-05/production-backlog.md). Automated gates must already be green (`.\scripts\signoff.ps1` or `./scripts/signoff.sh`).

---

## 0. Prerequisites

- [ ] Poetry env: `poetry install --with dev`
- [ ] Flutter SDK on `PATH` (`flutter --version`)
- [ ] `.env` with `FIGMA_ACCESS_TOKEN` (not committed)
- [ ] Target Flutter app exists (`flutter create` or existing repo)
- [ ] Offline gates green:

```bash
.\scripts\signoff.ps1
# or: ./scripts/signoff.sh
```

---

## 1. Figma connectivity

- [ ] `poetry run figma-flutter live-check --figma-url "<FIGMA_URL>" --dump --project-dir <PROJECT_DIR>` exits 0
- [ ] Dump written under `<PROJECT_DIR>/.debug/` (optional review)
- [ ] No secrets printed in console

Optional CI parity:

```bash
poetry run pytest -q -m live_figma
```

(requires `FIGMA_SMOKE_FILE_KEY`, `FIGMA_SMOKE_NODE_ID` in `.env`)

---

## 2. Production generate (deterministic path)

Use production profile (default for non-dry-run `generate` without `--allow-dev-profile`):

```bash
poetry run figma-flutter generate ^
  --figma-url "<FIGMA_URL>" ^
  --project-dir <PROJECT_DIR>
```

- [ ] Exit code 0
- [ ] Expected files under `lib/features/`, `lib/generated/`, `lib/theme/`, `lib/widgets/` as applicable
- [ ] `pubspec.yaml` lists asset dirs when icons/images exported

---

## 3. Dart / Flutter validation

```bash
cd <PROJECT_DIR>
dart format .
flutter analyze
```

- [ ] `flutter analyze` — 0 issues in generated scope (or documented waivers)
- [ ] App builds: `flutter build apk` or `flutter build web` (pick one target)

---

## 4. Runtime smoke

```bash
flutter run -d chrome
# or: flutter run -d <device>
```

- [ ] Screen renders without red error screen
- [ ] No obvious overflow at width **320** and **768** (resize browser / device)
- [ ] Navigation works if routing enabled in YAML
- [ ] Text scales with system font size (accessibility)

---

## 5. Custom-code preservation

1. Edit generated screen only inside `// <custom-code>` … `// </custom-code>`.
2. Re-run `generate` with same URL (production profile).

- [ ] Custom snippet preserved
- [ ] Edit **outside** zones + regenerate with production profile → clear error with line numbers (strict preservation)

---

## 6. Incremental sync

1. First `generate` (baseline snapshot in `.figma-flutter/snapshot.json`).
2. Change one repeated component in Figma (e.g. card text).
3. Second `generate`.

- [ ] Only expected files rewritten (widget vs layout per [limitations.md](../../limitations.md))
- [ ] Custom-code still intact

---

## 7. Sign-off

| Gate | Result (pass/fail) | Notes |
|------|-------------------|-------|
| Offline `signoff` script | | |
| Live Figma fetch | | |
| Production `generate` | | |
| `flutter analyze` | | |
| Runtime smoke | | |
| Preservation | | |
| Incremental sync | | |

**Overall:** [ ] **PASS** for MVP+ production path  |  [ ] **FAIL** (link issue / blocker)

---

## Waivers (if any)

Document intentional gaps vs literal `spec.md` — must match [spec-amendments.md](../../spec-amendments.md):

| Item | Waiver | Owner |
|------|--------|-------|
| | | |
