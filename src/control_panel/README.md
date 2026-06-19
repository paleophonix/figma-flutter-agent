# Purpose
Control panel: FastAPI host, optional disnake bot, ARQ workers, PostgreSQL jobs, public `/v1/jobs` REST + SSE, publish to GitLab/GitHub. Composition root: `lifespan` initializes long-lived resources into `app.state`; `/v1` handlers receive them only via FastAPI `Depends`.

# Usage Example
```bash
poetry install --with dev,control_plane
docker compose -f docker-compose.control-plane.yml --profile bundled-db up --build
poetry run alembic upgrade head
poetry run figma-flutter-control-panel
poetry run figma-flutter-worker
```

Discord `/generate` uses `.ai-figma-flutter.yml` like the local wizard. Set `generation.use_production_profile: true` in `.discord-bot.yml` for strict CI gates.

# LLM Context
Jobs live in PostgreSQL with `origin` (`discord`|`api`) and optional `principal`. Bad feedback: comment → ARQ `feedback_issue_job` (`bug` label). Good feedback → publish MR/PR + `feat` tracker issue. API clients authenticate via `X-API-Key` (env `CONTROL_PANEL_API_CLIENTS` JSON with sha256 hashes). Feat close posts last issue comment to `#changelog`; bug close replies in-thread to the user's feedback comment. SSE: `GET /v1/jobs/{id}/events` via Redis pub/sub. Telegram: outbound `sendMessage`; inbound callback button via `POST /webhooks/telegram`; `lifespan` auto-calls Bot API `setWebhook` when `TELEGRAM_BOT_TOKEN`, `telegram.channels`, HTTPS `internal.control_plane_url`, and `TELEGRAM_WEBHOOK_SECRET` (or `callback_secret`) are set.
