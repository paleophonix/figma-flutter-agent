---
name: research
description: >-
  Gathers external best practices, libraries, and patterns for a confirmed goal
  and codebase map. Use when the user invokes /research, asks for best practices,
  library options, or industry patterns before solution design.
disable-model-invocation: true
---

# Research (S3: RESEARCH)

Stage 3 of the CELESTIAL PIPELINE. Run **only** this stage — do not proceed to solution design, planning, or implementation.

**Prerequisites:** Confirmed goal from S1 (`/goal`) and affected modules from S2 (`/code`) should be in context. If missing, ask the user to run prior stages or provide them explicitly.

## Stage contract

<S3:RESEARCH>
**Objective:** Find best practices and standard approaches to avoid reinventing the wheel.
**Allowed:** Using `web_search` to look up libraries and patterns.
**Forbidden:** Formulating a final plan, writing code.
**Output:** A brief summary of best practices.

## Workflow

1. Restate the goal and key affected areas from S1/S2.
2. Run targeted `web_search` (and `WebFetch` when a source URL is known) for libraries, patterns, and established approaches relevant to the task.
3. Summarize findings — options and trade-offs only, no chosen solution yet.
4. Produce the output below. Stop — wait for user confirmation before S4.

## Output template

```markdown
## Context

**Goal:** [from S1]
**Affected areas:** [from S2]

## Best practices

| Topic | Practice | Source |
|-------|----------|--------|
| … | … | [link] |

## Library / tool candidates

| Name | Fit | Notes |
|------|-----|-------|
| … | … | … |

## Patterns worth considering

- …

## Anti-patterns to avoid

- …

## Open questions (if any)

1. …
```
