---
name: build
description: >-
  Figma→Flutter build phase: implement build_plan.json v2 in lib/, pubspec,
  theme. Strict step protocol; dart analyze + check.mjs gate. Use for /build
  after plan ready_for_build.
disable-model-invocation: true
---

# build

Implement **`build_plan.json`** (v2) in **`lib/`** per the plan contract. Gate on analyze + format + check.

Read plans from **`.agent/features/<feature>/`**. Write **`build_report.json`**. **ОТЧЁТ: СБОРКА** in chat.

## Scope (this phase only)

**Do:** `lib/`, pubspec, `build_report.json`, analyze.
**Stop before:** inspect / gaps / `fix_plan`.
**Forbidden in the same turn:** changing `layout_observation`, diagnosing, fixing.

## Inputs

- `build_plan.json` (v2)
- Flutter app root (`apps/agent`)
- `assets.manifest.json`, `fonts.required.json`, `fonts.report.json`
- `.agent/widget_catalog.json` — update when creating or changing widgets
- `.agent/token_catalog.json` — update when adding theme tokens

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Gate

**Action:** Read `build_plan.json`.

**Check:** `ready_for_build: true` and `node .agent/tools/check.mjs --phase plan` → exit 0.
**On fail:** return to **plan**. Never build from a red plan.

### Step 1 — Assets preflight

**Action:** If `fetch.meta.json` says `fetchMode: "json-only"` — run full **fetch** first. Confirm every `assets[].path` exists on disk.

**Check:** all planned assets present.
**On fail:** full fetch; still missing → stop, report the blocker.

### Step 2 — Scaffold (`screen_architecture`)

**Action:** Create the screen file from `files_to_create`: scaffold host, scroll model, pinned regions, stack layers (back → front), SafeArea, keyboard insets — exactly as planned.

**Check:** shell compiles mentally against the plan — every `stack_layers` entry and pinned region present in code.
**On fail:** plan vs tree conflict → back to **plan**, not silent improvisation.

### Step 3 — Widget tree + extracts

**Action:**

1. Map `widget_tree` nodes to widgets; `layout_props` from the plan (geometry from `cleaned.json`).
2. `extracted_widgets`: one Dart file per `action: create_new`; existing paths for `reuse_existing`; compose via `extract_ref`.
3. Honor `fidelity`: `image_bake` → the bound asset rendered via `Image.asset`/`SvgPicture.asset` (visual only; tap layer stays native); `stub` → placeholder per plan note.
4. Interactions: stub handlers (`onPressed: () {}`, controllers for `text_input`) — no business logic unless the user asked.

**Check:** every `files_to_create` path exists; every `widget_tree` node with `extract_ref` composes the extract; no plan-side node skipped.
**On fail:** finish the mapping — partial builds do not proceed to Step 4.

### Step 4 — Theme + tokens

**Action:** Apply `theme_bindings` via `dart_symbol` (`AppColors`, `AppTextStyles`, `AppSpacing`, `AppRadius`, `AppElevation`); `add_to_catalog` → append `.agent/token_catalog.json` entry **and** the `lib/theme/` const. No per-feature `*_colors.dart`.

**Check:** no anonymous `Color(0xFF…)`, literal radius/spacing in written files (rare justified literal → `// token-exempt` comment with a reason).
**On fail:** bind or add the token — do not ship raw values.

### Step 5 — Catalogs maintenance

**Action:**

1. New `lib/widgets/*.dart` → append `.agent/widget_catalog.json` entry (`W_*`, `parameters`, `used_by_features`). Reuse-only → add the feature slug to `used_by_features`.
2. New tokens → catalog entries per Step 4.
3. Bump `updated_at` (UTC, minute precision) on any catalog edit.

**Check:** every new widget file has a catalog entry; catalog `dart_file` paths exist.
**On fail:** sync the catalog now — stale catalogs poison the next plan.

### Step 6 — Fonts + pubspec

**Action:** Rename mismatched files in `assets/fonts/` to canonical names; run `.\.agent\tools\fonts.ps1`; add pubspec font/asset entries when `pubspec_entry_needed`.

**Check:** `fonts.report.json` has no `MISSING`; pubspec lists every planned asset dir.
**On fail:** download/rename per fonts tool; unresolved → note in `build_report` and the chat report.

### Step 7 — Analyze + format + gate

**Action:**

```bash
cd apps/agent && dart analyze && dart format .
```

Write `build_report.json`:

```json
{
  "version": 1,
  "feature": "<slug>",
  "plan_ref": { "version": 2, "ready_for_build": true },
  "files_written": ["lib/features/…"],
  "pubspec_touched": false,
  "analyze_exit_code": 0,
  "visual_next_step": "inspect or launch"
}
```

**Check:** `analyze_exit_code: 0` **and** `node .agent/tools/check.mjs --phase build` → exit 0.
**On fail:** stay in **build** until green — fix structure, not lint-suppress. Do not start inspect on red analyze.

### Step 8 — Report

**Action:** **ОТЧЁТ: СБОРКА** (RU): files written, reuse/created widgets, tokens added, pubspec touched, analyze result. End with the `Check:` line.

Optional: `flutter run` / capture PNG for **inspect** — only when analyze is 0.

---

## On failure routing

| Issue | Next |
|-------|------|
| Analyze errors | stay in **build** |
| Plan vs tree conflict | **plan** or **layout** — not silent patches |
| Missing assets | full **fetch**, update pubspec |
| Visual wrong (analyze clean) | **inspect** → **debug** → **fix** |
