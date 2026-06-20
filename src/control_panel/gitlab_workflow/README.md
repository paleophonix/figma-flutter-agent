# GitLab Issue Workflow

## Purpose

Orchestrate figma-flutter generation from GitLab Issues: parse Figma URLs,
enqueue generation/repair/publish, push issue branches, and post preview links.

## Usage Example

```python
from control_panel.gitlab_workflow import handle_gitlab_event

await handle_gitlab_event(payload, store=store, settings=settings, arq_pool=pool)
```

## LLM Context

Webhook payloads use GitLab ``object_kind`` (`issue`, `note`). Issue description
must contain one Figma frame URL; assignee must match ``gitlab_workflow.agent_username``.
Notes starting with ``/bug`` or ``/fix`` trigger repair or cold regen.
