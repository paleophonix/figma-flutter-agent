# Purpose
Control panel: FastAPI host, optional disnake bot, ARQ workers, PostgreSQL jobs, public `/v1/jobs` REST + SSE, publish to GitLab/GitHub. GitLab Issue-first workflow (`gitlab_workflow/`) is the primary v1 path when `discord.enabled: false`.

# Usage Example
```bash
poetry install --with dev,control_plane
docker compose -f docker-compose.control-plane.yml --profile bundled-db up --build
poetry run alembic upgrade head
poetry run figma-flutter-control-panel
poetry run figma-flutter-worker
```

GitLab project webhook: Issue events + Note events → `{control_plane_url}/webhooks/gitlab` with header `X-Gitlab-Token: {gitlab_webhook_secret}`.

Issue template: one Figma frame URL in description; assign `gitlab_workflow.agent_username`. Commands in notes: `/bug …` (repair + assignee), `/fix` (cold regen). Close issue → MR to `main` on branch `figma/issue-{iid}`.

Discord `/generate` uses `.ai-figma-flutter.yml` like the local wizard. Set `generation.use_production_profile: true` in `.discord-bot.yml` for strict CI gates.

# LLM Context
Jobs live in PostgreSQL with `origin` (`discord`|`api`|`gitlab`). GitLab jobs link to `gitlab_app_project_id` + `gitlab_issue_iid`, push preview URLs via `GET /preview/{job_id}?token=&mode=`, and post lifecycle notes through `gitlab_workflow/notify.py`. Legacy Discord feedback still uses `feedback_issue_job`. API clients authenticate via `X-API-Key`. SSE: `GET /v1/jobs/{id}/events` via Redis pub/sub.
