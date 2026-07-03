# Production backlog — code review 2026-05

**Owner:** engineering  
**Baseline:** `scripts/signoff.sh` / `scripts/signoff.ps1`  
**Last updated:** 2026-05-24

## P0 — blockers (strict production CI)

| ID | Task | Status |
|----|------|--------|
| P0-1 | `mypy src tests` — 0 errors | Done |
| P0-2 | `require_parse_complete` → `PipelineError`, CLI exit 2 | Done |
| P0-3 | `screen_paths` from `screen_file_path()` (no substring) | Done |
| P0-4 | E2E manual: real Figma → `generate` → `flutter analyze` | Open (template: [manual-acceptance.md](../production-readiness-2026-05/manual-acceptance.md), scripts `e2e-manual.*`) |

## P1 — production hardening

| ID | Task | Status |
|----|------|--------|
| P1-1 | Atomic `save_snapshot` (temp + replace) | Done |
| P1-2 | Parallel snapshot conflict test | Done |
| P1-3 | Signoff scripts: ruff + format + mypy + demo-signoff + pytest | Done |
| P1-4 | CI `test` job: `ruff format --check` | Done |
| P1-5 | Overflow regression @ width 320 | Done (codegen `_validate_narrow_viewport_layout`) |
| P1-6 | `avoid_fixed_sizes` strict in production | Done (wired via production profile + tests) |
| P1-7 | a11y: semantics on all interactives (strict codegen) | Done (`_assert_strict_interactive_semantics`) |
| P1-8 | Preservation: 5+ zones round-trip + write rollback integration | Done (zones test + `test_commit_planned_files_rolls_back_on_validation_failure`) |

## P2 — maintainability

| ID | Task | Status |
|----|------|--------|
| P2-1 | LLM retry: async or bounded executor (no `time.sleep` on default pool) | Done (`generate_async` + `asyncio.sleep`) |
| P2-2 | Dev-profile warning for non-strict JSON schema providers | Done (`structured_output_fallback` log + `strict: false` for OpenRouter/Google) |
| P2-3 | `PipelineDependencies` composition root | Done (`pipeline/deps.py`, `deps=` on `run_pipeline`) |
| P2-4 | README per module under `src/figma_flutter_agent/` | Done (`docs/modules/core.md` + package README map) |

## P3 — literal spec (post-MVP)

See `docs/spec-amendments.md` §8 checklist: Dev Mode API, bidirectional layout sync, Lottie, Variables modes, IDE plugins, webhook CI auto-PR.

## Sign-off commands

```bash
./scripts/signoff.sh          # Linux/macOS
.\scripts\signoff.ps1         # Windows
poetry run figma-flutter demo-signoff --strict
```
