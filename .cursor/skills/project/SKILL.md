---
name: project
description: >-
  Compares 2-3 high-level implementation approaches and selects one solution
  concept. Use when the user invokes /project, asks to choose an approach,
  compare options, or approve a solution direction before detailed planning.
disable-model-invocation: true
---

# Project (S4: PROJECT)

Stage 4 of the CELESTIAL PIPELINE. Run **only** this stage — do not proceed to detailed planning, spec writing, or implementation.

**Prerequisites:** Confirmed goal (S1 `/goal`), codebase map (S2 `/code`), and research summary (S3 `/research`) should be in context. If missing, ask the user to run prior stages or provide them explicitly.

## Stage contract

<S4:PROJECT>
**Objective:** Choose the optimal implementation path.
**Allowed:** Formulating 2–3 high-level approaches with pros and cons, selecting one viable option.
**Forbidden:** Detailing implementation, writing code.
**Output:** An approved solution concept.

## Workflow

1. Restate goal, affected areas, and key research findings in brief.
2. Draft 2–3 high-level approaches — trade-offs only, no step-by-step plan.
3. Recommend one option with clear rationale; ask the user to confirm or override.
4. Produce the output below. Stop — wait for user approval before S5.

## Output template

```markdown
## Context

**Goal:** [from S1]
**Constraints:** [from S2 + S3]

## Approach A — [name]

**Summary:** …
**Pros:** …
**Cons:** …

## Approach B — [name]

**Summary:** …
**Pros:** …
**Cons:** …

## Approach C — [name] (optional)

**Summary:** …
**Pros:** …
**Cons:** …

## Recommended choice

**Selected:** Approach [A/B/C] — [name]
**Rationale:** …

## Approved solution concept

[2–4 sentences: what we will build and how it fits the codebase — no implementation detail]

## Awaiting approval

Confirm this concept to proceed to `/plan`, or request changes.
```
