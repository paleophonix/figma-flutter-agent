# alembic

## Purpose

PostgreSQL schema migrations for the Discord control plane (`control_panel` SQLAlchemy models).

## Usage Example

```bash
poetry install --with control_plane
poetry run alembic upgrade head
poetry run alembic revision -m "describe_change" --autogenerate
```

Configuration lives in repo-root `alembic.ini` (`script_location = tools/alembic`). The database URL is resolved at runtime from `.discord-bot.yml` / env via `control_panel.config.load`.

## LLM Context

Do not embed migration SQL in prompts. Reference revision ids under `tools/alembic/versions/` and model changes in `src/control_panel/db/models.py` when planning schema work.
