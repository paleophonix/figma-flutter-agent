---
name: fix
description: >-
  Implement fixes after /debug triage: control plane, infra, runtime imports,
  CLI entry, observability. Pairs with /fix only — not diagnose-repair. Use for
  /fix, "почини" on Discord/worker/import/infra failures.
disable-model-invocation: false
---

@.claude/prompts/debug-common.md

# Fix Skill — implement after `/debug` only

Use **`/fix`** when the user wants **changes** after **`/debug`** triage.

**This flow is separate from diagnose-repair:**

```text
/debug → /fix           this skill
/diagnose → /repair     screen/compiler — do not use this skill
```

If the queue is about layout, IR, emitter, golden, or screen-specific compiler
laws — **stop** and tell the user to use **`/repair`** after **`/diagnose`**.

---

## Fix goal

Implement all in-scope **P0/P1/P2** items from `DEBUG TRIAGE REPORT` in one session.

---

## Hard limits

Never:

```text
hand-edit generated Dart in sandbox/*/lib or target Flutter lib/
update golden baselines to hide failure
screen/node-id/feature/text-value/fixture-specific production branches
magic layout coordinates for one screen
hardcode secrets or read .env in tests
unrelated refactors
```

Allowed: generic control-plane code, import-cycle breaks, env validation, worker/bot
fixes, CLI entry fixes, observability hooks.

---

## Entry modes

```text
CONTINUE     → after /debug or pasted DEBUG TRIAGE REPORT
INLINE DEBUG → /fix with traceback → run /debug inline, then fix
SINGLE ITEM  → user scoped one R-id
USER VERIFY  → user regens; agent runs targeted pytest only
```

---

## Workflow

### Step 0 — Queue

Source: `DEBUG TRIAGE REPORT` from `/debug`.

If missing, run `/debug` inline first.

```text
R1 [P0]: symptom -> root cause -> domain -> layer -> files -> proof
```

### Step 1 — Domain fix rules

| Domain | Fixes | Proof |
| ------ | ----- | ----- |
| **A. Control plane** | handlers, jobs, worker, config | `pytest tests/control_panel/…` |
| **B. Infra / env** | examples, validation, compose docs | process starts, health 200 |
| **C. Runtime / import** | break cycles, lazy imports, trim `__init__.py` | `python -c "import …"`, pytest |
| **D. CLI / entry** | CLI, fetch auth, pipeline bootstrap | pytest, clean log to first stage |
| **F. Observability** | metrics, logging | endpoint / unit test |

### Step 2 — Implement + verify

Surgical changes only. Run smallest relevant pytest after each group.

Do not run full signoff unless asked. User owns full generate/regen by default.

### Step 3 — Done or blocked

Stop when P0/P1/P2 done, blocked on secrets/tools, or fix would need a forbidden shortcut.

---

## Required output: FIX REPORT

```text
FIX REPORT

Queue source: DEBUG TRIAGE | inline debug
Domain(s):

Fixed:
  R1 [P0] [C]: symptom -> change -> proof

Infra / user actions:
Still blocked:
Verification:
Scope control:
Deferred:
Rollback:
```

---

## Routing (this flow only)

```text
/debug only  → report
/debug → /fix → this skill
```

Do not mention `/diagnose` or `/repair` except to say screen/compiler is out of scope.
