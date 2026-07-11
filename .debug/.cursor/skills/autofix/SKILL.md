---
name: autofix
description: >-
  /autofix — inspect → debug → fix as one strictly sequential chain.
  One RU chat report. No extra briefs.
disable-model-invocation: true
---

# autofix

Chain: **inspect → debug → fix**. Each step runs the **full phase skill protocol** — every internal step, every Check, corpus before fix.

**Strictly in order:** inspect finished → debug → fix. Do not write `fix_plan` during inspect, do not edit `lib/` during debug. One invocation = one cycle through this chain.

## Protocol

### Step 0 — Preflight

**Check:** `build_report` analyze = 0 · `figma.png`. A user screenshot (`compare_*.png`) is optional evidence.
**On fail:** red analyze → **build**.

### Step 1 — inspect (full protocol, incl. contract checks)

**Check:** `node .agent/tools/check.mjs --phase inspect` exit 0.
**On fail / no gaps:** clean screen → done: corpus **FIXED** for the feature (§ Auto-close), report, stop — not debug.
**Questions:** **УТОЧНЕНИЕ (inspect)**, stop the chain.

### Step 2 — debug (full protocol, incl. corpus OPEN on disk)

**Check:** `ready_for_fix: true` + `node .agent/tools/check.mjs --phase debug` exit 0.
**On fail:** stop — no fix without a green fix_plan.

### Step 3 — fix (full protocol, incl. re-inspect, corpus FIXED, promotion)

**Check:** analyze = 0 + `node .agent/tools/check.mjs --phase fix` exit 0 · resolved gaps gone from the fresh re-inspect.
**On fail:** items stay open; 2 attempts exhausted → fresh **debug** next cycle.

## Artifacts

**Write:** `inspect_observation.json`, `fix_plan.json`, `fix_report.json`, `lib/` during fix.

**Do not write:** `inspect_brief.md`, `visual_diff_tree.json`, per-phase reports in chat.

## Chat report (the only one)

**ОТЧЁТ: АВТОПОЧИНКА** (RU) — phases, gaps G*, queue F* resolved/open, analyze, corpus, `Check:` line, next step.

## Forbidden

fix without debug · **mixing inspect+debug+fix** · looping without a new PNG · +1px band-aids · `.debug/`
