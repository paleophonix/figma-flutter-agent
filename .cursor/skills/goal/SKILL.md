---
name: goal
description: >-
  Clarifies WHAT and WHY before any implementation; formulates SMART goals and
  Definition of Done. Use when the user invokes /goal, asks to define the task
  goal, acceptance criteria, or Definition of Done, or starts work with an
  ambiguous request.
disable-model-invocation: true
---

# Goal (S1: GOAL)

Stage 1 of the CELESTIAL PIPELINE. Run **only** this stage — do not proceed to research, planning, or code.

## Stage contract

<S1:GOAL>
**Objective:** Fully and unambiguously understand WHAT needs to be done and WHY.
**Allowed:** Reading source task files, clarifying questions to the user, formulating acceptance criteria (Definition of Done). Refine the goal using the SMART framework.
**Forbidden:** Proposing solutions, exploring code or documentation, generating code.
**Output:** A clearly stated goal and success criteria.

## Workflow

1. Read the user's request and any attached files.
2. Ask clarifying questions if WHAT or WHY is ambiguous.
3. Produce the output below. Stop — wait for user confirmation before S2.

## Output template

```markdown
## Goal

**What:** [concrete deliverable]
**Why:** [business or product value]

## SMART

| Criterion | Statement |
|-----------|-----------|
| Specific | |
| Measurable | |
| Achievable | |
| Relevant | |
| Time-bound | |

## Definition of Done

- [ ] …
- [ ] …

## Open questions (if any)

1. …
```
