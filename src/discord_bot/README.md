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
Jobs live in PostgreSQL. Bad feedback: comment in channel → ARQ `feedback_issue_job` (LLM ticket RU, `bug` label, screen+assets+debug bundle, issue in GitLab/GitHub). Good feedback → publish MR/PR + `feat` tracker issue. Feat close posts last issue comment to `#changelog` (`discord.changelog_channel_id`); bug close replies in-thread to the user's feedback comment. `/telegram` and `/autoclose` per-user prefs. Close via tracker webhook or user button (Discord/Telegram when autoclose=user).
Publish migrates sandbox output into remote repo paths then opens/updates PR/MR.
Screen debug artifacts use agent-repo `.debug/<project>/<feature>/`.
