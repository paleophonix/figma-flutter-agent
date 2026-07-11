---
name: autobuild
description: >-
  /autobuild — layout → plan → build as one strictly sequential chain.
  One RU chat report. No extra meta/briefs.
disable-model-invocation: true
---

# autobuild

Chain: **layout → plan → build**. Each step runs the **full phase skill protocol** (`layout`, `plan`, `build`) — every internal step, every Check.

**Strictly in order:** phase N finished (JSON + flag + `check.mjs` exit 0) → only then phase N+1. Do not mix phase work in one pass. Between phases, do **not** touch the next phase's artifacts.

Path: `.agent/features/<feature>/`. Rules: `pipeline-architecture.mdc` § Phase order, `spec-contract.mdc`, `widget-reuse.mdc`, `token-reuse.mdc`, `reports-locale.mdc`.

## Protocol

### Step 0 — Preflight

No `figma.png` / `fetchMode: json-only` → full fetch:

```powershell
cd apps/agent
.\.agent\tools\fetch.ps1 -Url "<url>" -Out .\.agent\features\<feature>
```

**Check:** full fetch on disk **and** `fonts.report.json` without `missing` / `download_failed`.
**On fail:** stop and ask — never source from `.debug/`. Re-run `fonts.ps1` if only fonts failed.

### Step 1 — layout (full protocol)

**Check:** `ready_for_plan: true` + `open_questions` empty + `node .agent/tools/check.mjs --phase layout` exit 0.
**On fail:** emit **УТОЧНЕНИЕ** (RU) and stop the chain — not plan.

### Step 2 — plan (full protocol)

**Check:** `ready_for_build: true` + `node .agent/tools/check.mjs --phase plan` exit 0.
**On fail:** emit **УТОЧНЕНИЕ** and stop — not build.

### Step 3 — build (full protocol)

**Check:** `analyze_exit_code: 0` + `node .agent/tools/check.mjs --phase build` exit 0.
**On fail:** stay in build until green or report the blocker.

## Artifacts

**Write only:** `layout_observation.json`, `screen_contract.json`, `build_plan.json`, `lib/…` + `build_report.json`, catalogs when new widgets/tokens appear.

**Do not write:** `layout_brief.md`, `plan_brief.md`, per-phase reports in chat.

## Chat report (the only one)

```text
ОТЧЁТ: АВТОСБОРКА

Фича: …
Фазы: layout ✓ plan ✓ build ✓  (или стоп на …)
Контракт: A* покрыто …, I* покрыто …
Кратко: …
Analyze: 0 | ошибка
Check: 0 failures | <failing lines>
Дальше: /autofix | уточнение | готово
```

## Forbidden

Skipping phases · **mixing phases** · inspect/debug/fix inside autobuild · `.debug/`
