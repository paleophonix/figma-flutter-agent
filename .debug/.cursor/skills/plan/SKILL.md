---
name: plan
description: >-
  Flutter architecture plan: screen scaffold, widget tree, extracts, theme/assets,
  interaction stubs, contract coverage in build_plan.json. Strict step protocol.
  Use for /plan after layout ready_for_plan.
disable-model-invocation: true
---

# plan

**Architecture intent before Dart** — screen IR + widget blueprint + file contract.

Translates **layout** (what the screen *is*) and **screen_contract** (what it *must do*) into **build_plan.json** (how Flutter *assembles* it). **build** writes `lib/` from this file only.

**Write `build_plan.json` to `.agent/features/<feature>/`.** One **ОТЧЁТ: ПЛАН** in chat.

## Scope (this phase only)

**Do:** `build_plan.json` (+ corpus/catalog reads).
**Stop before:** `lib/`, `build_report`, inspect.
**Forbidden in the same turn:** writing Dart, fixing bugs, inspect.

## Inputs

| Input | Role |
|-------|------|
| `layout_observation.json` | Regions, `ui_role`, `interactive`, `interaction` |
| `screen_contract.json` | ТЗ items to cover (`spec-contract.mdc`) |
| `cleaned.json` | Geometry, Auto Layout — sole source of sizes/hierarchy |
| `assets.manifest.json` | Asset paths and node bindings |
| `fonts.required.json` | Font faces for the pubspec plan |
| `.agent/widget_catalog.json` | Reusable widgets — before extracts |
| `.agent/token_catalog.json` | Design tokens — before `theme_bindings` |
| `tokens.observed.json` | Observed values from fetch — match against catalog |
| `.agent/corpus/features/<feature>.yaml` | Case ids for this screen — if it exists |
| `.agent/corpus/families.yaml` | Mechanism names for the layout→family map |

**Honor layout semantics.** Do not downgrade a layout **button** to static `Text`. Do not invent controls where layout marked `unknown` without a `plan_notes` entry.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Gate

**Action:** Read `layout_observation.json` and `screen_contract.json`.

**Check:** `ready_for_plan: true` and `node .agent/tools/check.mjs --phase layout` → exit 0.
**On fail:** return to **layout** (or resolve P0 / `open_questions` with the user). Do not plan on a red gate.

### Step 1 — Corpus playbook (known failure modes)

**Action:**

1. If `.agent/corpus/features/<feature>.yaml` exists — open **each** listed `cases/<id>.yaml` (explicit paths, no glob).
2. Match layout nodes/regions to likely mechanisms via `families.yaml`:

| On screen | `family_id` (check the case) |
|-----------|------------------------------|
| line item + thumb/image | `image_asset_bound_to_wrong_node` |
| cart/list row + stepper | `flex_cross_stretch_inflates_fixed_child` |
| section titles / card padding | spacing from `cleaned.json` |
| footer / sheet chrome | pinned stack, modal child |
| chip / badge + image | raster parent vs leaf |

3. If `index/<family_id>.yaml` exists — one case row `project: agent`, prefer the same `feature`.
4. Lessons → `plan_notes[]` and concrete `layout_props` / `stack_layers` / `assets[]` decisions.

**Check:** feature manifest cases (when the manifest exists) are all read; lessons reflected in `plan_notes`.
**On fail:** first run without corpus is fine — state `Corpus: 0 кейсов` in the report.

### Step 2 — Token match

**Action:** Read `.agent/token_catalog.json` + `tokens.observed.json` (`token-reuse.mdc`). Match observed colors, typography, spacing, radii, shadows to catalog `value` (spacing/radius ±0.5). Draft `theme_bindings[]` with `catalog_id`, `dart_symbol`, `action` (`use_existing` | `add_to_catalog` | `alias_existing` | `inherit_material`).

**Check:** no anonymous color/spacing/radius left unbound in the upcoming `widget_tree`.
**On fail:** add `add_to_catalog` bindings — do not leave raw hex for build to improvise.

### Step 3 — `screen_architecture`

**Action:** Decide the shell before leaf widgets:

- `host`: `scaffold` | `modal_bottom_sheet` | `dialog` | `full_bleed`
- `scroll_model`: `none` | `single_list` | `custom_scroll` | `nested_scroll` | `horizontal_list`
- `pinned_regions`, `stack_layers[]` (back → front: `backdrop`, `content`, `sticky_footer`, `scrim`)
- `safe_area`, `keyboard_insets` (`resize` | `scroll_padding` | `n/a`)

**Check:** every layout **region** maps to a slot (scroll body, pinned, stack layer).
**On fail:** unmapped region → re-read layout; architecture ambiguity → back to **layout** or ask.

### Step 4 — `widget_tree` (+ fidelity)

**Action:** Per significant node (layout `nodes` + `cleaned.json`):

| Field | Source |
|-------|--------|
| `figma_id` | tree |
| `layout_ui_role` | from `layout_observation` |
| `widget` | Flutter kind (`FilledButton`, `TextField`, `SvgPicture`, …) |
| `layout` | `row` / `column` / `stack` / `positioned` / `expanded` / `flexible` |
| `layout_props` | gap, alignment, fixed w/h — **from cleaned.json only** |
| `theme_ref` | token key or `theme.textTheme.*` |
| `child_ids` | tree order |
| `extract_ref` | if instance of `extracted_widgets[].id` |
| `fidelity` | `native` (default) \| `image_bake` \| `stub` — per `figma-flutter-mapping.mdc` § Fidelity |

Auto Layout mapping: HORIZONTAL→`Row` · VERTICAL→`Column` · Wrap→`Wrap` · Fill→`Expanded`/`Flexible` · Absolute→`Stack`+`Positioned` · long lists→`ListView`/slivers tied to `scroll_model`.

Nodes deliberately not built (invisible helpers, redundant wrappers) → `omitted[]` with `figma_ids` + `reason`. **Silent drops are forbidden** — check.mjs enforces conservation.

**Check:** every layout node's `figma_ids` land in `widget_tree` / `extracted_widgets.root_figma_ids` / `omitted[]`. `image_bake` nodes have an `assets[]` binding; no `image_bake` on interactive nodes.
**On fail:** add the missing mapping or an `omitted[]` entry with a reason.

### Step 5 — `extracted_widgets` (reuse first)

**Action:** Read `.agent/widget_catalog.json` (`widget-reuse.mdc`):

1. Match layout clusters to catalog entries (`tags`, `reuse_when`, `ui_role`).
2. Prefer `action: reuse_existing` + `catalog_id`; `extend_existing` with optional params when justified in `plan_notes`.
3. `create_new` only when no catalog match — say why in `plan_notes`.
4. Catalog empty but `lib/widgets/` non-empty → scan Dart, seed the catalog, then plan.

Per extract: `id`, `catalog_id`, `action`, `dart_file`, `class_name`, `root_figma_ids[]`, `reuse_count`, `parameters[]`.

**Check:** no `create_new` that duplicates an existing catalog pattern.
**On fail:** switch to `reuse_existing` / `extend_existing`.

### Step 6 — `assets` + fonts + `interactions`

**Action:**

1. `assets[]` from `assets.manifest.json`: `path`, `figma_id`, `widget` (`Image.asset` / `SvgPicture.asset`), `pubspec_entry_needed`.
2. Fonts from `fonts.required.json` → pubspec plan.
3. `interactions[]` — stubs only: `figma_id`, `kind` (`tap` | `submit` | `toggle` | `dismiss` | `scroll` | `text_input`), `handler: "stub"`, `note`; `text_input` → `controller: create|reuse`.

**Check:** every layout `interactive: yes` node has an `interactions[]` entry or an interactive widget; every asset path exists in the manifest (never invented).
**On fail:** add entries; missing files on disk → note "full fetch before build".

### Step 7 — Contract coverage

**Action:** For **every** `screen_contract` acceptance `A*` and interaction `I*` add a `contract_coverage[]` entry:

```json
{ "contract_id": "A1", "covered_by": ["figma_id | dart file | interaction id"], "note": "…" }
```

or an explicit omission: `{ "contract_id": "S2", "omitted": true, "reason": "…" }`.

**Check:** no contract item without coverage or a reasoned omission (check.mjs enforces).
**On fail:** cover it or ask the user — silence is not an option.

### Step 8 — `files_to_create`, `responsive`, `accessibility`, `plan_notes`

**Action:**

1. `files_to_create` — explicit full list (screen, widgets, `pubspec.yaml` when touched).
2. `responsive`: `breakpoint_dp: 600`, `changes[]`.
3. `accessibility`: `Semantics` / tooltips; tap targets ≥48dp where `interactive: yes`.
4. `plan_notes`: layout P1 carries, stubs, deferred API, corpus lessons, `create_new` justifications.

**Check:** `files_to_create` covers every extract `dart_file` with `action: create_new` and the screen file.
**On fail:** complete the list.

### Step 9 — Write artifact + gate

**Action:** Write `build_plan.json`:

```json
{
  "version": 2,
  "feature_slug": "<slug>",
  "layout_ref": { "observation_version": 2, "ready_for_plan": true },
  "screen_architecture": {},
  "widget_tree": { "root_id": "<figma_id>", "nodes": [] },
  "extracted_widgets": [],
  "theme_bindings": [],
  "assets": [],
  "interactions": [],
  "omitted": [],
  "contract_coverage": [],
  "files_to_create": [],
  "responsive": { "breakpoint_dp": 600, "changes": [] },
  "accessibility": [],
  "plan_notes": [],
  "ready_for_build": false
}
```

Set `ready_for_build: true` only when Steps 3–8 checks all passed.

**Check:** `node .agent/tools/check.mjs --phase plan` → exit 0.
**On fail:** fix the plan per the failing lines; re-run. Do not hand off to build.

### Step 10 — Report

**Action:** **ОТЧЁТ: ПЛАН** (RU): shell + scroll model, reuse N / create M widgets, tokens reuse/add counts, `Corpus: N кейсов, уроки: …`, contract coverage summary, `ready_for_build`. End with the `Check:` line.

---

## Forbidden

- Writing Dart or running `dart analyze`
- Geometry not backed by `cleaned.json`
- Pixel band-aids (`+1 padding` hacks) — fix flex/scroll in the plan
- Re-litigating button vs textbox — that was **layout**
- Ignoring `assets.manifest.json` / inventing asset paths
- Silent node drops (use `omitted[]`) · silent contract gaps (use reasoned omission)

## Handoff to build

| State | Next |
|-------|------|
| `ready_for_build: true` + check exit 0 | **build** |
| missing assets on disk | full **fetch**, then **build** |
| architecture ambiguity | revise plan or return to **layout** |
