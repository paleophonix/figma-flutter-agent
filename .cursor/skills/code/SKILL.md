---
name: code
description: >-
  Maps existing codebase components and integration points for a confirmed goal.
  Use when the user invokes /code, asks which modules or files are affected, or
  needs a codebase impact analysis before research or planning.
disable-model-invocation: true
---

# Code (S2: BASE)

Stage 2 of the CELESTIAL PIPELINE. Run **only** this stage — do not proceed to external research, solution design, planning, or implementation.

**Prerequisite:** A confirmed goal from S1 (`/goal`) should be in context. If missing, ask the user to run `/goal` first or state the goal explicitly.

## Stage contract

<S2:BASE>
**Objective:** Understand which components already exist in the codebase and how the new feature will integrate with them.
**Allowed:** Analyzing relevant parts of the project (`codebase_search`, `read_file`), identifying affected modules.
**Forbidden:** Exploring external sources, generating new solutions.
**Output:** List of existing modules/files that will be affected.

## Workflow

1. Restate the confirmed goal in one sentence.
2. Search and read relevant project areas (SemanticSearch, Read, Grep).
3. Map affected modules, files, and integration points — no solution proposals yet.
4. Produce the output below. Stop — wait for user confirmation before S3.

## Output template

```markdown
## Goal (confirmed)

[one-sentence restatement from S1]

## Affected modules

| Module / path | Role today | Expected touch |
|---------------|------------|----------------|
| `path/to/module` | … | … |

## Integration points

- …

## Existing patterns to reuse

- …

## Out of scope (for now)

- …

## Open questions (if any)

1. …
```
