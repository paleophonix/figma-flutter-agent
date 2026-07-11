---
name: batch
description: >-
  /batch — run autobuild over .agent/screens.yaml, one screen at a time,
  strictly sequential. Blocked screens are recorded, not skipped silently.
  One RU chat report.
disable-model-invocation: true
---

# batch

Run **autobuild** over a screen manifest — one screen fully, then the next. Never interleave two screens.

## Manifest: `.agent/screens.yaml`

```yaml
screens:
  - feature: niyama_order
    url: "https://www.figma.com/design/…?node-id=1-2"
    status: pending        # pending | built | blocked | done
    note: ""
```

The user owns the list and priorities; the agent owns `status` + `note`.

## Protocol

### Step 0 — Manifest gate

**Action:** Read `.agent/screens.yaml`. Missing → ask the user for the screen list (feature slugs + Figma URLs); write the manifest.

**Check:** at least one `status: pending` screen.
**On fail:** nothing to do — report and stop.

### Step 1 — Per screen (in manifest order)

For each `pending` screen, strictly one at a time:

1. Set `AGENT_FEATURE` context to the screen's `feature`.
2. Run the **autobuild** chain (full protocols: layout → plan → build).
3. Outcome:
   - all gates green → `status: built`, `note: analyze 0`
   - **УТОЧНЕНИЕ** raised (layout/plan questions) → `status: blocked`, `note:` the question ids — **continue to the next screen**
   - build blocker (assets, fonts, analyze) → `status: blocked`, `note:` the blocker — continue

**Check (per screen):** status updated in the manifest before starting the next screen.
**On fail:** do not start screen N+1 with screen N's status unrecorded.

### Step 2 — Wrap-up

**Action:** Update the manifest. Collected УТОЧНЕНИЕ questions from all blocked screens go into **one** consolidated block at the end of the report — grouped by screen.

## Chat report (the only one)

```text
ОТЧЁТ: ПАКЕТ

Экранов: N (built: X, blocked: Y, осталось: Z)
| Фича | Статус | Кратко |
|------|--------|--------|
| …    | built  | analyze 0 |
| …    | blocked| Q1: кнопка или label? |

УТОЧНЕНИЕ (по заблокированным): …
Дальше: ответы на вопросы → /batch снова | /autofix по экранам
```

## Rules

- **One screen = one full autobuild** — no partial layout for screen B while screen A builds.
- Blocked ≠ skipped: every blocked screen has its questions in the report.
- `/batch` re-run after answers: only `pending` + `blocked` screens are processed; `built`/`done` untouched.
- inspect/debug/fix are **not** part of batch — run `/autofix` per screen afterwards.
- No `*_brief.md`, no per-screen chat reports — one ОТЧЁТ: ПАКЕТ.

## Forbidden

Parallel screens · silent skips · fixing during batch · `.debug/`
