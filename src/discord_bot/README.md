# Purpose
Discord control plane: FastAPI host, disnake bot, ARQ workers, PostgreSQL jobs, publish to GitLab/GitHub.

# Usage Example
```bash
poetry install --with dev,control_plane
# Bundled Postgres (data on host .data/postgres):
docker compose -f docker-compose.control-plane.yml --profile bundled-db up --build
# External Postgres (set database.mode: external in .discord-bot.yml):
docker compose -f docker-compose.control-plane.yml up --build
poetry run alembic upgrade head
poetry run figma-flutter-discord
poetry run figma-flutter-worker
```

# LLM Context
Jobs live in PostgreSQL. Configure `database.mode` in `.discord-bot.yml`: `bundled` (Docker profile `bundled-db` + `FIGMA_CP_PG_PASSWORD`) or `external` (`database.url` / `FIGMA_CP_DATABASE_URL`). Generation runs in ARQ worker via `run_pipeline`.
Publish migrates sandbox output into remote repo paths then opens/updates PR/MR.
Screen debug artifacts use agent-repo `.debug/<project>/<feature>/`.
