# Audit baseline

- Captured: `2026-06-13T06:09:33.110794+00:00`
- Git SHA: `756d14baccd6f683416f7a6a1810ecc29229d559`
- Pytest: `22 failed, 2384 passed, 70 skipped, 2 deselected in 556.95s (0:09:16)` (exit=1)

## Commands to refresh

```bash
poetry run figma-flutter doctor
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter fixture-ir-validate
poetry run figma-flutter fixture-geometry-check
poetry run pytest -q -m "not live_figma"
```

