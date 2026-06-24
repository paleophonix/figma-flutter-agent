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
Notes starting with ``/bug`` or ``/regen`` trigger repair or cold regen. Legacy alias: ``/fix``.
Lifecycle comments: generation started (on enqueue), preview ready, failure, MR ready.
Preview links are public HTTP URLs on the control panel (`/preview/{job_id}?token=&mode=`).
When ``preview.release_build`` is false (default), links proxy to ``flutter run -d web-server``.
When ``preview.release_build`` is true, the worker runs ``flutter build web --release`` after
generate and the proxy serves static assets (faster open, slower ``/regen``).
Issue branch names come from `gitlab_workflow.issue_branch_template` (or `gitlab.issue_branch_template` override).
Placeholders: `{issue_iid}`, `{feature_slug}`, `{job_id}`.
When ``gitlab_workflow.commit_debug_artifacts`` is true, issue-branch commits also include
``.debug/<feature>/`` copied from agent ``.debug/screen/<project>/<feature>/`` (triage bundle).
