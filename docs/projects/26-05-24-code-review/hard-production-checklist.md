# Hard production checklist (code review 2026-05)

Source: hard code review of `src/figma_flutter_agent` vs `docs/spec.md` + `docs/spec-amendments.md`.

**Executive verdict:** MVP+ / production sign-off OK under amendments. Literal spec gaps documented as waivers.

---

## P0 — blockers for «жёсткий» production

- [x] **Analyze scope:** `validation.analyze_scope: all_planned` (production default) — analyze full planned Dart set
- [x] **Rollback атомарность:** `_restore_backup` fail-fast + `GenerationError` with partial-restore detail
- [x] **Spec §7.3 mobile bands:** `isWideLayout` (width > 480) drives column reflow; four-band grid; shell padding per band
- [x] **Dry-run data leakage:** default dry-run output is summary-only; full design payload requires `--dump-design`
- [x] **Path traversal guard:** `DartWriter` validates resolved write targets remain inside `project_dir`
- [x] **Observability accuracy:** `log_stage` logs `failed` on exception, `completed` on success only
- [x] **Centralized secret redaction:** shared `redaction.redact_secrets()` used by errors and Loguru format

## P1 — serious, next release

- [x] **spec23 design_system:** strict gate includes `app_radius.dart`, `app_elevation.dart`
- [x] **Snapshot concurrency:** `save_snapshot(..., expected_version=)` optimistic locking
- [x] **LLM dev profile:** CLI warning when provider lacks strict JSON schema support
- [x] **`validate_planned_dart_files`:** `package:<name>/` import prefix validation
- [x] **Incremental sync UX:** region hashes (`layout_region_hash`, `cluster_hashes`) documented in `docs/limitations.md`
- [x] **Product default:** deterministic codegen documented (`spec-amendments` §10, `limitations.md`)
- [x] **Fail-fast auto_route codegen:** `run_pub_get` / `run_build_runner` with `require_dart_sdk` in production write stage
- [x] **Mypy strict hot paths:** writer, connector, sync.diff, parser.tree, layout_*, codegen, validation

## P2 — quality improvements

- [ ] **Component variants §14:** extend beyond `variant_props.py` heuristics
- [ ] **Cupertino parity:** form controls / navigation vs Material
- [x] **`merge_custom_code`:** unmatched blocks inserted after imports
- [x] **Figma Variables API:** 403 fallback documented; full integration post-MVP (`spec-amendments` §7.6)
- [x] **Observability:** `run_id` / correlation id per pipeline run (`new_run_id`, CLI + logs)
- [x] **CLI errors:** `_handle_cli_exception` — domain vs boundary vs unexpected
- [x] **Corrupt snapshot:** quarantine + pipeline warning; production `sync.fail_on_corrupt_snapshot`

## P3 — hygiene

- [x] **README:** package map documents `errors.py`, `observability.py`, `redaction.py`
- [ ] **README:** `schemas.py` module doc (optional)
- [ ] **spec23 connectivity:** stable contract test vs introspection
- [ ] **codegen_checks:** AST-based validation (optional)
- [x] **Refactor `run_pipeline`:** `pipeline/llm.py`, `pipeline/incremental.py`, `pipeline/helpers.py`
- [x] **Snapshot no-op skip:** skip persist when sync has nothing to write and hashes unchanged

---

## Spec §23 — acceptance (current)

| Criterion | Status |
|-----------|--------|
| Figma connectivity | ✅ REST; live — `live-check --figma-url` |
| Dev Mode / CSS synthesis | ✅ REST `rest_css_synthesis` (strategy B) |
| Responsive Flutter UI | ✅ `isWideLayout` reflow + four-band grid |
| Reusable widgets | ✅ |
| Design system | ✅ generated; strict gate includes radius/elevation |
| Asset export | ✅ |
| Responsive breakpoints | ✅ constants + mobile-large reflow |
| Flutter optimization | ✅ |
| Production-ready code | ✅ production profile |
| Developer preservation | ✅ custom-code + strict_preservation |

---

## Pre-release smoke (manual)

```bash
poetry run pytest -q -m "not live_figma"
poetry run figma-flutter demo-signoff --strict
poetry run figma-flutter live-check --figma-url "..." --dump --project-dir ../demo_app
poetry run figma-flutter generate --figma-url "..." --project-dir ../demo_app
cd ../demo_app && dart format . && flutter analyze && flutter run -d chrome
```

---

## Definition of Done (hard production)

- [x] P0 closed or waived in `spec-amendments.md`
- [x] `demo-signoff --strict` green (offline)
- [x] `pytest -m "not live_figma"` green
- [ ] Generate on real Figma frame → analyze green in generated scope (manual)
- [x] Custom-code preservation (automated tests)
- [x] Orphan edit outside zones → `GenerationError` with `--strict`
- [x] `docs/spec-amendments.md` reflects waivers
