---
name: plan
description: >-
  Turns an approved solution concept into a technical spec with a numbered
  checklist and writes it to docs/projects/. Use when the user invokes /plan,
  asks for a spec, task breakdown, or implementation checklist before coding.
disable-model-invocation: true
---

# Plan (S5: PLAN)

Stage 5 of the CELESTIAL PIPELINE. Run **only** this stage — do not write application code or start implementation.

**Prerequisites:** Approved solution concept from S4 (`/project`) plus prior context from S1–S3. If the concept is not approved, ask the user to run `/project` first or approve explicitly.

## Stage contract

<S5:PLAN>
**Objective:** Turn the solution into a step-by-step instruction and persist it locally.
**Allowed:** Creating a detailed technical specification, breaking work into subtasks (3–5), converting the plan into a numbered **CHECKLIST**, creating a project file at `docs/projects/<project_folder>/<project_name>.md`.
**Forbidden:** Writing final application code, using GitHub/Git issues, starting implementation without a written file.
**Output:** A created specification file with a ready checklist.

## Workflow

1. Confirm the approved solution concept from S4.
2. Choose `project_folder` and `project_name` (kebab-case; ask if unclear).
3. Draft the spec: goal, scope, affected modules, 3–5 subtasks, numbered checklist with DoD per item.
4. **Write the file** to `docs/projects/<project_folder>/<project_name>.md` using the Write tool — do not only paste in chat.
5. Report the file path and checklist summary. Stop — wait for user confirmation before S6 (work/implementation).

## Spec file template

Use this structure when creating `docs/projects/<project_folder>/<project_name>.md`:

```markdown
# [Project title]

> Status: ready for execution
> Date: YYYY-MM-DD
> Pipeline: S5 PLAN — derived from approved S4 concept

---

## 1. Goal

**What:** …
**Why:** …

## 2. Approved concept (from S4)

…

## 3. Scope

### In scope
- …

### Out of scope
- …

## 4. Affected modules

| Path | Change |
|------|--------|
| … | … |

## 5. Subtasks (3–5)

1. …
2. …
3. …

## 6. CHECKLIST

- [ ] 1. … — DoD: …
- [ ] 2. … — DoD: …
- [ ] 3. … — DoD: …
- [ ] 4. … — DoD: … (optional)
- [ ] 5. … — DoD: … (optional)

## 7. Risks and assumptions

- …
```

## Rules

- **File first:** Implementation must not start until the spec file exists on disk.
- **No GitHub issues:** Track work in the spec checklist only.
- **No app code:** Spec and checklist only; code belongs in S6.
- **Checklist is authoritative:** S6 executes checklist items in order and marks them done in this file.
