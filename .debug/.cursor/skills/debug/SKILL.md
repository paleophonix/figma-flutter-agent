---
name: debug
description: >-
  Diagnosis after inspect: fix_plan.json + RU triage report. Corpus OPEN only for recurring mechanisms.
  Strict step protocol. No lib/ edits.
disable-model-invocation: true
---

# debug (agent kit diagnose)

Use after **`/inspect`** when `inspect_observation.json` has gaps and **`aligned_with_user: true`**.

**inspect** finds gaps — **no diagnosis**. **debug** classifies → fix queue.

**Separate from the repo compiler flow:**

```text
/debug → /fix         this kit (apps/agent)
/diagnose → /repair   compiler pipeline — not this skill
```

**Diagnosis-only** — no `lib/` edits, no `dart analyze`. Code changes belong to **`/fix`**.

Legacy: if only `visual_observation.json` exists, read it as inspect output.

## Scope (this phase only)

**Do:** triage → `fix_plan.json` + corpus OPEN **only when the mechanism is recurring or lesson-worthy** (see `corpus-law.mdc` § Skip corpus).
**Stop before:** `lib/`, fix, re-inspect.
**Forbidden in the same turn:** fixing code, analyze, corpus FIXED.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Gates + active feature

**Action:** Resolve the feature (`apps/agent/.env` → `AGENT_FEATURE` or user input). Confirm artifact freshness: `fetch.meta.json`, `build_report.json`, `inspect_observation.json`.

**Check:** `build_report.json` → `analyze_exit_code: 0` **and** `inspect_observation.json` → `aligned_with_user: true`.
**On fail:** red analyze → **build**; not aligned → **inspect**. State the blocker; do not diagnose stale artifacts.

### Step 1 — Read evidence (fixed order)

**Action:** Read in this order:

```text
inspect_observation.json          # queue source: gaps G*, contract_checks fail
figma.png, compare_*.png          # user screenshot, if provided
layout_observation.json, screen_contract.json, build_plan.json, build_report.json
cleaned.json, lib/… (read-only)
```

Plus when present: `assets.manifest.json`, `fonts.report.json`, `fetch.meta.json`.

**Forbidden input:** `figma-flutter-agent/.debug/` — compiler cache only.

**Check:** every gap `G*` and every failed contract check has been read against at least two sources (render + tree/plan).
**On fail:** do not diagnose from memory or one screenshot.

### Step 2 — Corpus lookup

**Action:** Per `corpus-law.mdc` + `.cursor/skills/corpus/SKILL.md`:

```text
symptom → family_id (mechanism, not "overflow")
→ .agent/corpus/families.yaml
→ .agent/corpus/index/<family_id>.yaml   # when it exists
→ ONE .agent/corpus/cases/<case_id>.yaml
```

Never glob `cases/*.yaml`. From FIXED cases read: `contract.expected/actual`, `repair.summary`, `repair.verification`.

**Check:** every symptom got a family lookup attempt (`unclassified` is a valid outcome, with a reason).
**On fail:** classify by mechanism before layering.

### Step 3 — Map symptoms to layers

**Action:** Group by **mechanism**, not screen region. Per root cause:

| layer | typical fix owner |
|-------|-------------------|
| `layout` | re-run **layout** — perception wrong |
| `plan` | **build_plan.json** |
| `build` | implementation ≠ plan |
| `visual` | flex/scroll/stack in `lib/` |
| `assets` | fetch, pubspec, paths |
| `fonts` | assets/fonts, pubspec |
| `contract` | ТЗ item failed — route to the owning layer above + mark contract id |

```yaml
root_cause:
  symptom: ...
  family_id: ...           # from families.yaml or unclassified
  layer: layout|plan|build|visual|assets|fonts
  contract_ids: []         # A*/I* when a contract check failed
  figma_ids: []
  confidence: high|medium|low
  evidence:
    - path: .agent/features/<feature>/inspect_observation.json
      summary: ...
  corpus_status: ready_for_record|playbook_only|none|trivial
  fix_summary_draft: >
    2–3 sentences for /fix — structural intent, not a file list
```

User chat notes → evidence, never the sole classifier.

**Check:** every `G*` and failed contract check maps to exactly one root cause (several symptoms may share one).
**On fail:** unmapped symptom = incomplete triage.

### Step 4 — Repair queue

**Action:** List every distinct bug class as `F*` — do not collapse to one winner. Sort P0 → P1 → P2; respect dependencies (missing asset before pixel nits).

**Check:** queue covers all root causes; each item has `fix_actions` (structural intent).
**On fail:** complete the queue.

### Step 5 — Write `fix_plan.json` + gate

**Action:**

```json
{
  "version": 2,
  "feature": "<slug>",
  "queue_source": "inspect_observation + build_plan",
  "items": [
    {
      "id": "F1",
      "priority": "P0",
      "layer": "visual",
      "family_id": "optional",
      "contract_ids": [],
      "figma_ids": [],
      "symptom": "…",
      "fix_actions": ["Structural: wrap modal body in Flexible — see build_plan scroll_model"],
      "corpus_status": "record_open|playbook_only|none|trivial",
      "corpus_case_id": "YYYY-MM-DD-<slug>",
      "fix_summary_draft": "…"
    }
  ],
  "execution_order": ["F1", "F2"],
  "blocked": [],
  "ready_for_fix": true
}
```

`corpus_status` here is the **outcome** of Step 6 (`record_open` — OPEN case written; `playbook_only` — existing case informs; `none`). Set `ready_for_fix: false` if P0 items lack evidence. **Do not write** `visual_diff_tree.json`.

**Check:** `node .agent/tools/check.mjs --phase debug` → exit 0.
**On fail:** fix the artifact; re-run.

### Step 6 — Corpus (only when lesson-worthy)

**Action:** OPEN a compact case **only** when `corpus_status: ready_for_record` **and** the bug is **not trivial** (`corpus-law.mdc` § Skip corpus): recurring mechanism, or a pattern the next screen must not repeat.

When trivial → set item `corpus_status: none` in `fix_plan.json`; skip YAML.

When recording: `cases/YYYY-MM-DD-<mechanism>.yaml` (`status: OPEN`), append id to `corpus/features/<feature>.yaml` per corpus skill.

**FORBIDDEN:** YAML for forgot-tool / typo / one-off config · YAML in chat only · deferring OPEN to /fix when the mechanism is recurring and non-trivial.

**Check:** report `Corpus recorded: <paths>` or `Corpus: none — trivial|unclassified` for every queue item.
**On fail:** if recurring and non-trivial but no YAML on disk — debug turn is not done.

### Step 7 — Report + handoff

**Action:** **ОТЧЁТ: ТРИАЖ** (RU): queue F* with priorities and layers, corpus recorded, `ready_for_fix`. End with the `Check:` line.

Default: report + `fix_plan.json`, **no lib/ edits**. Batch trigger (`/fix`, "чиним") → hand the queue to **fix**.

---

## Anti-patching (mandatory)

Forbidden: +1px padding stacks, magic `Color(0xFF…)`, screen-name/`figmaId` one-off hacks, copying from `.debug/`.
Required: structural fixes tied to `build_plan` + `cleaned.json` facts; repeatable across similar layouts.

## Forbidden

- `dart analyze` · editing `lib/` (unless the user explicitly asks) · compiler `src/` changes
