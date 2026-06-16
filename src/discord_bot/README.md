# Purpose
Discord control plane for `/generate`, preview feedback, and GitLab orchestration.

# Usage Example
```bash
poetry install --with dev,discord
cp .discord-bot.yml.example .discord-bot.yml
poetry run figma-flutter-discord
```

# LLM Context
Jobs live in SQLite (`DISCORD_BOT_DB_PATH`). Pipeline runs call `figma_flutter_agent.pipeline.run.run_pipeline`.
Screen debug artifacts use agent-repo `.debug/<project>/<feature>/`.
