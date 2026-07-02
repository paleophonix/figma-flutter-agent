---
name: task
description: Writes issue/ticket body for the current task using a fixed JTBD template in Russian. Use when the user invokes /task, asks for ticket content, issue description, or task card text without commentary.
disable-model-invocation: true
---

# Task

## Purpose

Produce ready-to-paste ticket content for the **current task** from conversation context.

## Allowed

- Read conversation history, attached files, and open task context.
- Infer missing fields from codebase, config, and prior discussion when evidence exists.
- Use `TBD` only when a field cannot be inferred and the user did not supply it.

## Forbidden

- Do not add preamble, postscript, explanations, or meta-commentary.
- Do not wrap output in code fences unless the user explicitly asks.
- Do not propose implementation steps or code.
- Do not create GitHub/GitLab issues — output text only.

## Workflow

1. Identify the active task from the latest user intent and session context.
2. Resolve ticket ID: use the user-provided ID; otherwise `TBD`.
3. Fill every section below from evidence; keep wording concise and product-oriented.
4. Return **only** the filled template — nothing before or after it.

## Output

Return exactly this structure, filled in:

```markdown
## (ID) Краткая суть задачи 
**Пиши на языке продакта без лишних технических деталей, непонятных сокращений и по-русски!**
- **JTBD-работа** «Когда я [ситуация], я хочу [действие], чтобы [результат]».
- **Описание UX фичи списком шагов**
- **Стэк**
- **Интеграции**
- **План реализации**
- **Критерии приемки** (DoD)
- **Метрики успеха** (KPI)
```

### Field rules

| Field | Content |
| --- | --- |
| `(ID)` | Ticket/issue id or `TBD` |
| Краткая суть | One line — what ships and for whom |
| JTBD-работа | One JTBD sentence in the quoted format |
| Фича | User-visible capability or change |
| Стэк | Languages, frameworks, services touched |
| Интеграции | External APIs, webhooks, third-party systems; `—` if none |
| Критерии приемки | Bullet list of testable done conditions |
| Метрики успеха | Bullet list of measurable KPIs or `—` if not applicable |
