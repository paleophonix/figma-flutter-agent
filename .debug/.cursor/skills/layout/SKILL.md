---
name: layout
description: >-
  Perception sync → layout_observation.json + screen_contract.json. Full fetch
  required. Strict step protocol. One RU chat report. No layout_brief.md.
disable-model-invocation: true
---

# layout

**Synchronize what the user sees with what the machine reads** — before any widget plan or Dart.

Triangulate three sources:

| Source | Role |
|--------|------|
| `cleaned.json` | Geometry, hierarchy, Auto Layout — machine facts |
| `tokens.observed.json` | Unique colors, spacing, radii from fetch — optional perception hints |
| `figma.png` | Visual truth — pill vs field, overlays, scroll bands |
| User context | Business intent, ТЗ, corrections, "this is not clickable" |

**Write all outputs to `.agent/features/<feature>/`** (`AGENT_FEATURE` in `.env` or `-Out` on fetch).

## Scope (this phase only)

**Do:** perception sync → `layout_observation.json` + `screen_contract.json`.
**Stop before:** plan / `build_plan` / `lib/`.
**Forbidden in the same turn:** widget choices, Dart, inspect, debug, fix.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue to the next step.

### Step 0 — Fetch preflight

**Action:** Read `fetch.meta.json`. Confirm `fetchMode: "full"` and `figma.png` on disk. If missing or `json-only`:

```powershell
.\.agent\tools\fetch.ps1 -Url "<figma-url>" -Out .\.agent\features\<feature>
```

Re-clean only (when raw already exists):

```powershell
.\.agent\tools\fetch.ps1 -Clean .\.agent\features\<feature>\raw.json -Output .\.agent\features\<feature>\cleaned.json
```

Optional fonts audit: `.\.agent\tools\fonts.ps1 -AuditOnly -Feature .\.agent\features\<feature>`

**Check:** `fetchMode: "full"` + `figma.png` exists + `cleaned.json` parses.
**On fail:** fetch failed (token, API) → **stop and ask the user**. Never copy from `figma-flutter-agent/.debug/` or another feature.

### Step 1 — Collect user context (ТЗ)

**Action:** Gather everything the user said about this screen: inline message, `user_context.md`, invoke comments. Quote key phrases verbatim into `user_context_summary`.

**Check:** `user_context_summary` written, or explicitly `"none provided"`.
**On fail:** n/a — absence is a valid, recorded state.

### Step 2 — Screen regions (top down)

**Action:** Split the frame into human regions before leaf detail: status/system chrome · header/nav · hero/promo · scrollable body · pinned footer/CTA · overlays (modal, sheet, scrim, tooltip).

Per region: `region_id`, `human_label`, `figma_ids[]`, `layout_mode`, `scroll_role` (`scrolls` | `pinned` | `none`).

**Check:** every visible band of `figma.png` belongs to exactly one region; no region without `figma_ids`.
**On fail:** re-walk the PNG top-down; unclear band → `open_questions`.

### Step 3 — Significant nodes

**Action:** For each interactive or visually meaningful cluster record:

- `figma_ids[]`, `human_label`, `figma_type` (`FRAME`, `TEXT`, `INSTANCE`, …)
- `ui_role` — `button` | `text_field` | `label` | `icon` | `image` | `list_item` | `chip` | `toggle` | `divider` | `chrome` | `decorative` | `scrim` | `unknown`
- `interactive` — `yes` | `no` | `unknown`; `interaction` — `tap` | `type` | `toggle` | `scroll` | `drag` | `none`
- `disabled_look` — `yes` | `no` | `n/a`
- `vision_match` — `aligned` | `mismatch` | `unclear` (tree vs `figma.png`)
- `user_note`, `confidence` (`high`|`medium`|`low`), `needs_confirmation` (bool)

**Semantic rule:** record `ui_role: button` only when tree + vision agree; otherwise it is a mismatch (Step 4).

**Check:** every region from Step 2 has its significant nodes listed; no `ui_role` outside the enum.
**On fail:** cover the missed region before continuing.

### Step 4 — Mismatches

**Action:** Every `vision_match: mismatch` or user-vs-tree conflict → `alignment_issues[]`:

```json
{
  "id": "M1",
  "severity": "P0",
  "figma_ids": ["123:456"],
  "symptom": "Tree: TEXT node; vision: pill CTA; user: primary button",
  "tree_says": "TEXT 'Оформить'",
  "vision_says": "Filled pill, centered label",
  "user_says": "Main checkout button",
  "proposed_ui_role": "button",
  "resolution": "unresolved"
}
```

Severity: **P0** blocks plan (wrong control kind, missing overlay) · **P1** note for plan · **P2** cosmetic.

**Check:** every mismatch from Step 3 has an `M*` entry with severity.
**On fail:** file the missing entries — silent mismatches are drift.

### Step 5 — Screen contract (ТЗ → artifact)

**Action:** Create or update `screen_contract.json` per `spec-contract.mdc`:

1. From user ТЗ: `jtbd`, `acceptance[]` (`A*`, each with `verify_by`), `interactions[]` (`I*`, each with `expect` + `level`), `states[]`, `out_of_scope[]`. Quote the user, do not paraphrase into new scope.
2. No user ТЗ → derive: every `interactive: yes` node → `I*` with `level: stub`; baseline acceptance `A1` = "экран соответствует figma.png без P0/P1 расхождений", `verify_by: inspect`; mark `source: design-derived`.
3. Ambiguous requirement → `open_questions` (contract) + Step 6 question. Never invent a default.

**Check:** `node .agent/tools/check.mjs --phase contract` → exit 0.
**On fail:** fix the contract shape; re-run the check.

### Step 6 — Open questions → ask the user

**Action:** Anything with `confidence: low`, `needs_confirmation: true`, `vision_match: unclear`, unresolved P0/P1, or a contract ambiguity → `open_questions[]`:

```json
{
  "id": "Q1",
  "figma_ids": ["123:456"],
  "question": "Это primary CTA или декоративный label?",
  "why_blocked": "Tree TEXT vs pill on figma.png",
  "options": ["button — navigates checkout", "label — no tap", "unsure — need product call"],
  "default_if_silent": null
}
```

If `open_questions` is non-empty: emit **УТОЧНЕНИЕ (layout)** (RU, per `reports-locale.mdc`) with concrete questions — region/node, 2–3 options, what is blocked — and **stop the protocol here**. After answers: update `user_context_summary`, `resolution`, the contract, and re-run from Step 3 for affected nodes.

**Check:** `open_questions` empty **or** УТОЧНЕНИЕ emitted and the turn ended.
**On fail:** silent completion with unclear P0 semantics is forbidden.

### Step 7 — Write artifact + gate

**Action:** Write `layout_observation.json`:

```json
{
  "version": 2,
  "feature": "<slug>",
  "sources": { "fetch_mode": "full", "has_figma_png": true, "user_context_provided": true },
  "user_context_summary": "…",
  "screen_summary": "One-line purpose",
  "regions": [],
  "nodes": [],
  "alignment_issues": [],
  "open_questions": [],
  "risks_for_plan": [],
  "ready_for_plan": false
}
```

Set `ready_for_plan: true` only when: no unresolved P0 · `open_questions` empty · `figma.png` used · contract written · no pending УТОЧНЕНИЕ.

**Check:** `node .agent/tools/check.mjs --phase layout` → exit 0.
**On fail:** fix the artifact per the failing lines; re-run. Do not hand off to plan.

### Step 8 — Report

**Action:** **ОТЧЁТ: РАЗМЕТКА** (RU): `screen_summary`, regions, what is clickable, contract summary (A*/I* counts), `ready_for_plan`, open questions. End with the `Check:` line quoting check.mjs result.

---

## Outputs

`layout_observation.json` + `screen_contract.json` + chat report. **Do not write** `layout_brief.md`.

## Forbidden

- Writing Dart or `build_plan.json`
- Choosing Flutter widget classes (`ElevatedButton`, …) — that is **plan**
- Mutating `cleaned.json` or re-fetching to "fix" the tree — record a mismatch only
- Completing layout without `figma.png`
- Corpus case writes
- **Any use of `figma-flutter-agent/.debug/`** — compiler cache; not kit input

## Handoff to plan

| State | Next |
|-------|------|
| `ready_for_plan: true` + check exit 0 | **plan** |
| P0 mismatches unresolved | **УТОЧНЕНИЕ** → user → re-run **layout** |
| `open_questions` non-empty | **ask the user first** — never auto-**plan** |
