# Release gate matrix (MVP+)

**Canonical contract:** [spec-amendments.md](../../spec-amendments.md)  
**Last updated:** 2026-05-24

## Automated (required on every PR)

| Gate | Command | CI job |
|------|---------|--------|
| Lint + format | `ruff check .` + `ruff format --check .` | `test` |
| Types | `mypy src tests` | `test` |
| Offline unit tests | `pytest -q -m "not live_figma"` | `test` |
| Offline sign-off bundle | `./scripts/signoff.sh` | `test` |
| §23 fixtures + dart analyze | `demo-signoff --strict` | `acceptance` |
| Flutter integration | `test_flutter_integration.py` | `flutter-integration` |
| Live Figma (when secrets set) | `pytest -m live_figma` | `live-figma` |

Windows local equivalent: `.\scripts\signoff.ps1`

## Manual (required once per release candidate)

See [manual-acceptance.md](manual-acceptance.md):

- Real Figma frame → `generate` → `flutter analyze` → `flutter run`
- Custom-code + incremental sync on same project

## Code review backlog

Tracked in [production-backlog.md](../code-review-2026-05/production-backlog.md).

**MVP+ automated bar:** all P0–P2 items **Done** except P0-4 (manual E2E).

**Literal spec.md 10/10:** P3 tier (Dev Mode API, bidirectional sync, …) — post-MVP.
