# Summarize step skill

## Purpose

Step 7/7 — read-only case archivist. Translates review verdict into RU product ticket (when completed) and EN engineering handoff (always). Does not re-judge.

```text
review = decides
summarize = translates + archives + routes
```

## Usage example

Orchestrator invokes summarize only after `review.decision` is CONTINUE or STOP. On LOOP, emit blocked without running the model. Orchestrator owns `task_completed`, `forensic_completed`, and `screen_completed`.

## LLM context

Single model (×1), no ensemble. Agent writes `agent_task_completed_recommendation` only. Inject `law_label_map_ru` from `.opencode/context/law-label-map-ru.yaml` for ticket prose.

Tests: selected at **plan**, written/run at **repair**, proven at **review**, archived in **dev** — see spec § test regression lifecycle.
