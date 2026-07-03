# CI honesty: Stages 0–2

Ratchet-first governance for lint and type-check gates without changing compiler behavior.

## Goals

- **Stage 0:** Coverage map (informative, not a threshold gate) + stable pytest/planner baselines.
- **Stage 1:** Single Poetry dev dependency source; ruff clean on `src/`.
- **Stage 2:** Mypy ratchet + content-identity fingerprint linters; narrow `except` at pipeline/LLM boundaries.

Stage 3 (god-file splits) is out of scope here.

## Dev dependencies

`[tool.poetry.group.dev.dependencies]` is the only dev source. Runtime extras remain under `[project.optional-dependencies]` (`preview`, `control_plane`, `discord`).

## Coverage (Stage 0)

Sign-off runs pytest with coverage after the main gate suite:

```bash
poetry run pytest -q -m "not live_figma" \
  --cov=figma_flutter_agent \
  --cov-report=term-missing \
  --cov-report=json:logs/coverage/coverage.json
```

No fail-on-threshold. JSON lands under `logs/coverage/` (gitignored).

## Mypy ratchet (Stage 2)

`scripts/lint_mypy.py` runs `mypy src tests`, parses errors, and compares fingerprints to `tests/fixtures/lint/mypy_baseline.txt`.

Fingerprint key:

```text
path|line|code|message_hash
```

- **Fails** only on **new** fingerprints (not in baseline).
- **Removed** fingerprints are burn-down wins (gate stays green).
- CI `lint` job and sign-off call `lint_mypy.py`, not raw `mypy`.

Refresh baseline after intentional burn-down:

```bash
poetry run python scripts/lint_mypy.py --migrate-baseline
```

Optional burndown JSON:

```bash
poetry run python scripts/lint_mypy.py --write-burndown logs/lint/mypy_burndown.json
```

## Content-identity fingerprints (Stage 2)

`scripts/lint_baseline.py` keys violations by **snippet hash + category** only:

```text
snippet_hash|category
```

- File relocate with the same snippet does **not** fail the gate.
- New snippet content (new hash) **does** fail.

Regenerate all four codex baselines after the identity change:

```bash
poetry run python scripts/lint_dart_in_python.py --migrate-baseline
poetry run python scripts/lint_hardcoded_colors.py --migrate-baseline
poetry run python scripts/lint_regex_dart_surgery.py --migrate-baseline
poetry run python scripts/lint_settings_purity.py --migrate-baseline
```

## Verification checklist

```bash
poetry install --with dev
poetry run ruff check .
poetry run ruff format --check .
poetry run python scripts/lint_dart_in_python.py
poetry run python scripts/lint_settings_purity.py
poetry run python scripts/lint_hardcoded_colors.py
poetry run python scripts/lint_regex_dart_surgery.py
poetry run python scripts/lint_mypy.py
poetry run pytest -q -m "not live_figma" --cov=figma_flutter_agent
```

Acceptance:

- ruff on `src/` = 0 errors
- all five lint gates exit 0
- pytest count not worse than pre-change baseline
- relocate-safe fingerprint gates
- new mypy error breaks CI
