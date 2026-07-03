# Code Review Remediation Plan (2026-05)

**Status:** Phase 1 (production blockers) in progress — Sprint 12 MVP gates done; hard review P0 partially closed (2026-05-23)  
**Source:** Hard code review vs `docs/spec.md`

## Sprint 0 — Blockers

- [x] 0.1–0.8 (see git history)

## Sprint 1 — Production hardening

- [x] 1.1–1.13 (see git history)

## Sprint 2 — Spec parity

### 2.1 Structural dedup (§7.5)

- [x] 2.1.1 Structural subtree hashing + `cluster_id` on clean tree
- [x] 2.1.2 Figma component `instance_count >= 2` widget hints for LLM
- [x] 2.1.3 Tests: `tests/test_dedup.py`

### 2.2 Navigation (§7.8)

- [x] 2.2.1 `routing` config (`none` | `go_router`, default `none`)
- [x] 2.2.2 `app_router.dart.j2` + renderer integration
- [x] 2.2.3 Conditional `go_router` pubspec dependency
- [x] 2.2.4 Prompt update when routing enabled

### 2.3 Accessibility (§7.9)

- [x] 2.3.1 `accessibility_label` / `accessibility_hint` on clean tree nodes
- [x] 2.3.2 WCAG contrast + small-font warnings in pipeline
- [x] 2.3.3 LLM prompt Semantics + textScaler rules
- [x] 2.3.4 Tests: `tests/test_accessibility.py`

### 2.4 Incremental sync (§16–17)

- [x] 2.4.1 Snapshot store `.figma-flutter/snapshot.json`
- [x] 2.4.2 Diff engine → selective file writes
- [x] 2.4.3 CLI `--no-sync` + config `sync.enabled`
- [x] 2.4.4 Tests: `tests/test_sync.py`, `tests/test_navigation.py`

**Sprint 2 acceptance:** `poetry run python -m pytest -v -ra` green (65 tests).

## Sprint 3 — Production-ready gates (2026-05 review)

### 3.1 Transactional generation

- [x] 3.1.1 `WriteBatch` / `PubspecUpdateBatch` with commit + rollback
- [x] 3.1.2 Pipeline: validate before commit; rollback includes `pubspec.yaml`
- [x] 3.1.3 Tests: `tests/test_transactional.py`, updated `tests/test_writer.py`, `tests/test_pubspec.py`

### 3.2 Renderer imports

- [x] 3.2.1 Screen imports extracted widgets; widget template imports theme + `flutter_svg`
- [x] 3.2.2 PascalCase → snake_case fix for widget filenames (`PrimaryButton` → `primary_button`)
- [x] 3.2.3 Tests: `tests/test_renderer.py`

### 3.3 Type safety & CI

- [x] 3.3.1 `mypy src tests` → 0 errors (`pydantic.mypy` plugin, typed fixes)
- [x] 3.3.2 Mypy gate in `.github/workflows/ci.yml`

### 3.4 Dry-run semantics

- [x] 3.4.1 `--dry-run` skips LLM (`needs_llm = not dry_run and ...`)
- [x] 3.4.2 Tests: `tests/test_pipeline_async.py`

**Sprint 3 acceptance:** 78 tests green, ruff green, mypy green.

## Sprint 4 — Spec depth & integration gates

### 4.1 Dev Mode / style extraction (§5.1, §5.2)

- [x] 4.1.1 Extended `NodeStyle`: opacity, effects, gradients, elevation, `styleName`, `cssProperties`
- [x] 4.1.2 `parser/styles.py` — shadows, gradients, CSS-like properties
- [x] 4.1.3 `parser/components.py` — variant/state metadata for instances
- [x] 4.1.4 Tests: `tests/test_styles.py`, `tests/test_components.py`

### 4.2 Styles & Components API (§5.1)

- [x] 4.2.1 `FigmaConnector.fetch_styles()` / `fetch_components()`
- [x] 4.2.2 Pipeline `asyncio.gather` for styles + components
- [x] 4.2.3 Tests: `tests/test_connector.py`

### 4.3 Deterministic codegen contracts

- [x] 4.3.1 `generator/codegen_checks.py` — Semantics, textScaler, fixed-width warnings
- [x] 4.3.2 Wired into pipeline before file commit
- [x] 4.3.3 Tests: `tests/test_codegen_checks.py`

### 4.4 Flutter analyze integration

- [x] 4.4.1 Minimal Flutter skeleton fixture with `flutter_svg`
- [x] 4.4.2 End-to-end render + `validate_dart_project()` test (skipped when SDK missing)
- [x] 4.4.3 Tests: `tests/test_flutter_integration.py`

**Sprint 4 acceptance:** pytest + ruff + mypy green; integration test runs when `dart`/`flutter` available.

## Sprint 5 — Navigation, responsive enforcement, AutoRoute

### 5.1 Prototype navigation (§7.8)

- [x] 5.1.1 `parser/prototype.py` — parse Figma `reactions`, index frames, build route plan
- [x] 5.1.2 Pipeline fetches missing destination nodes and passes `navigationHints` to LLM
- [x] 5.1.3 Destination screen stubs for prototype targets
- [x] 5.1.4 Tests: `tests/test_prototype.py`

### 5.2 Multi-route templates

- [x] 5.2.1 GoRouter / Navigator 2.0 templates emit all discovered routes
- [x] 5.2.2 AutoRoute: `@RoutePage()` injection, `@AutoRouterConfig`, `app_router.gr.dart` stub
- [x] 5.2.3 `build_runner` + `auto_route_generator` dev deps when auto_route selected
- [x] 5.2.4 Tests: updated `tests/test_navigation.py`, `tests/test_pubspec.py`

### 5.3 Responsive enforcement

- [x] 5.3.1 `GeneratedScreenShell` + `AppLayoutExtension` in theme (`maxWebWidth` now effective)
- [x] 5.3.2 Codegen gate requires `GeneratedScreenShell` when responsive enabled
- [x] 5.3.3 LLM prompt updated to use shell

**Sprint 5 acceptance:** 96 tests green, ruff green, mypy green.

## Sprint 6 — Destination screens, overlays, codegen pipeline

### 6.1 Destination LLM generation

- [x] 6.1.1 `generator/destinations.py` — generate screens for prototype destination frames
- [x] 6.1.2 `routing.generate_destinations` config (default `true`)
- [x] 6.1.3 Pipeline: LLM per destination, stubs only on failure
- [x] 6.1.4 Tests: `tests/test_destinations.py`

### 6.2 Prototype overlay actions

- [x] 6.2.1 `OVERLAY`, `SWAP`, `SCROLL_TO` in `collect_prototype_links`
- [x] 6.2.2 Navigation hints describe overlay/modal vs push
- [x] 6.2.3 Tests: updated `tests/test_prototype.py`

### 6.3 Constraint-based responsive lint

- [x] 6.3.1 Warn when FILL-sized nodes lack `Expanded`/`Flexible` in generated screens
- [x] 6.3.2 Fixed height count warnings
- [x] 6.3.3 Tests: updated `tests/test_codegen_checks.py`

### 6.4 build_runner integration

- [x] 6.4.1 `generator/codegen.py` — `run_pub_get`, `run_build_runner`
- [x] 6.4.2 Pipeline runs pub get + build_runner before analyze when `auto_route`
- [x] 6.4.3 Tests: `tests/test_codegen.py`, `tests/test_auto_route_integration.py`

**Sprint 6 acceptance:** 103+ tests green, ruff green, mypy green.

## Sprint 7 — Destination assets, overlay codegen, multi-screen validation

### 7.1 Destination frame asset export

- [x] 7.1.1 `merge_asset_manifests()` in `schemas.py`
- [x] 7.1.2 Pipeline exports assets from prototype destination frames and merges manifests
- [x] 7.1.3 `build_destination_trees()` applies merged manifest to all destination trees
- [x] 7.1.4 Tests: `tests/test_navigation_codegen.py` (`merge_asset_manifests`)

### 7.2 Overlay navigation codegen

- [x] 7.2.1 `generator/navigation_codegen.py` — `PrototypeAction`, `build_prototype_actions()`
- [x] 7.2.2 `prototype_navigation.dart.j2` — overlay → `showModalBottomSheet`, push → `context.push` / `Navigator.push`
- [x] 7.2.3 Pipeline renders `lib/core/prototype_navigation.dart` when prototype links exist
- [x] 7.2.4 LLM prompt references `PrototypeNavigation` helpers
- [x] 7.2.5 Tests: `tests/test_navigation_codegen.py`

### 7.3 Accessibility validation across all screens

- [x] 7.3.1 `validate_generated_dart()` accepts multiple clean trees
- [x] 7.3.2 Per-screen `GeneratedScreenShell` check when responsive enabled
- [x] 7.3.3 Overlay helper warning when `require_overlay_helpers=True`
- [x] 7.3.4 Pipeline passes primary + destination trees to validation
- [x] 7.3.5 Tests: `tests/test_codegen_checks_screens.py`

### 7.4 CI Flutter integration job

- [x] 7.4.1 `flutter-integration` job in `.github/workflows/ci.yml`
- [x] 7.4.2 Runs `test_flutter_integration.py` and `test_auto_route_integration.py` with Flutter SDK

**Sprint 7 acceptance:** 108 tests green (2 skipped without local Flutter), ruff green, mypy green.

## Sprint 8 — Transitions, Dev Mode paints, destination parity

### 8.1 Prototype transition parsing & codegen

- [x] 8.1.1 `parser/transitions.py` — parse Figma transition duration/easing/type
- [x] 8.1.2 `PrototypeLink.transition` + multi-action `reactions.actions[]` support
- [x] 8.1.3 `prototype_navigation.dart.j2` — `PageRouteBuilder` with fade/slide/scale transitions
- [x] 8.1.4 Navigation hints include transition metadata
- [x] 8.1.5 Tests: `tests/test_transitions.py`, updated `tests/test_prototype.py`, `tests/test_navigation_codegen.py`

### 8.2 Dev Mode published style paint resolution

- [x] 8.2.1 `collect_style_node_ids()` / `build_style_paint_index()` in `parser/styles.py`
- [x] 8.2.2 Pipeline fetches style definition nodes and resolves paints into clean tree
- [x] 8.2.3 `style_paint_index` threaded through `build_clean_tree()`
- [x] 8.2.4 Tests: updated `tests/test_styles.py`

### 8.3 Destination LLM parity

- [x] 8.3.1 `build_destination_trees()` returns trees + widget hints
- [x] 8.3.2 `generate_destination_screens()` reuses pre-built trees and retries once on failure
- [x] 8.3.3 Pipeline passes cached destination trees/hints to LLM generation
- [x] 8.3.4 Tests: updated `tests/test_destinations.py`

**Sprint 8 acceptance:** pytest + ruff + mypy green.

## Sprint 9 — GoRouter transitions, SWAP/SCROLL helpers

### 9.1 GoRouter custom transitions

- [x] 9.1.1 `build_route_transitions()` maps prototype transitions to route paths
- [x] 9.1.2 `app_router.dart.j2` uses `CustomTransitionPage` when transition metadata exists
- [x] 9.1.3 Pipeline passes route transitions into router rendering
- [x] 9.1.4 Tests: updated `tests/test_navigation_codegen.py`

### 9.2 SWAP / SCROLL deterministic helpers

- [x] 9.2.1 `prototype_navigation.dart.j2` — `context.replace` for swap (go_router), `pushReplacement` otherwise
- [x] 9.2.2 `prototype_scroll_targets.dart.j2` + `PrototypeScrollTargets.scrollTo()` for SCROLL_TO
- [x] 9.2.3 LLM prompt documents scroll target registration
- [x] 9.2.4 Tests: swap/scroll helper generation

**Sprint 9 acceptance:** pytest + ruff + mypy green.

## Sprint 10 — AutoRoute parity & dark theme

### 10.1 AutoRoute transitions & navigation

- [x] 10.1.1 `app_auto_route.dart.j2` — `CustomRoute` with fade/slide/scale transitions
- [x] 10.1.2 `PrototypeAction.destination_route_class` for typed AutoRoute navigation
- [x] 10.1.3 `prototype_navigation.dart.j2` — `context.router.push/replace` for auto_route
- [x] 10.1.4 Tests: updated `tests/test_navigation_codegen.py`

### 10.2 Dark theme generation

- [x] 10.2.1 `dark_mode.enabled` config in `.ai-figma-flutter.yml`
- [x] 10.2.2 `AppTheme.dark()` via `ColorScheme.fromSeed` + `Brightness.dark`
- [x] 10.2.3 Pipeline passes `generate_dark_mode` to theme renderer
- [x] 10.2.4 Tests: `tests/test_tokens.py`

**Sprint 10 acceptance:** pytest + ruff + mypy green.

## Sprint 11 — App bootstrap & AI UX suggestions

### 11.1 Generated app bootstrap

- [x] 11.1.1 `main.dart.j2` — `MaterialApp` / `MaterialApp.router` wired to theme + routing
- [x] 11.1.2 `render_app_bootstrap()` in renderer; pipeline emits `lib/main.dart`
- [x] 11.1.3 Incremental sync includes `lib/main.dart` on tree changes
- [x] 11.1.4 Tests: `tests/test_renderer.py`, updated `tests/test_flutter_integration.py`

### 11.2 AI UX suggestions

- [x] 11.2.1 `parser/ux.py` — touch target, nesting depth, spacing consistency heuristics
- [x] 11.2.2 Pipeline collects UX suggestions for primary + destination trees
- [x] 11.2.3 Tests: `tests/test_ux.py`

**Sprint 11 acceptance:** pytest + ruff + mypy green.

## Sprint 12 — Pixel validation scaffold & acceptance closure

### 12.1 Figma reference export & layout metrics

- [x] 12.1.1 `validation/reference.py` — export PNG + metadata, layout metric warnings
- [x] 12.1.2 `validation.export_figma_reference` config (default `false`)
- [x] 12.1.3 Pipeline exports reference image; snapshot stores `reference_image_hash`
- [x] 12.1.4 Tests: `tests/test_reference.py`

### 12.2 Golden test scaffold

- [x] 12.2.1 `golden_screen_test.dart.j2` + `render_golden_test()`
- [x] 12.2.2 `validation.generate_golden_test` config (default `false`)
- [x] 12.2.3 Incremental sync includes `test/golden/` on tree changes
- [x] 12.2.4 Tests: updated `tests/test_renderer.py`

### 12.3 Spec §23 acceptance verification

- [x] 12.3.1 `tests/test_acceptance.py` — module-level acceptance checks
- [x] 12.3.2 Remediation plan marked complete (Sprints 0–12)

**Sprint 12 acceptance:** pytest + ruff + mypy green.

---

## Phase 1 — Production blockers (hard review 2026-05-23)

### 1.1 Deterministic layout & `lib/generated/`

- [x] 1.1.1 `generator/layout_renderer.py` — `CleanDesignTree` → `lib/generated/{feature}_layout.dart`
- [x] 1.1.2 Pipeline always plans layout file (LLM screen code remains parallel path)
- [x] 1.1.3 Screen delegates to `{Feature}Layout` when `generation.use_deterministic_screen` (default true)

### 1.1b Enforced cluster widgets (§7.5)

- [x] 1.1b.1 `generator/widget_extractor.py` — cluster ≥ N → `lib/widgets/{name}_widget.dart`
- [x] 1.1b.2 Layout references `const ProductCardWidget()` instead of inlined duplicates
- [x] 1.1b.3 Config `generation.enforce_cluster_widgets` + `cluster_min_count`
- [x] 1.1b.4 Tests: `tests/test_widget_extractor.py`

### 1.2 Responsive breakpoints (§7.3)

- [x] 1.2.1 `AppBreakpoints` in `app_layout.dart.j2` (320–480 / 481–768 / 769–1024 / 1025+)
- [x] 1.2.2 `GeneratedScreenShell` uses `LayoutBuilder` + breakpoint padding/max width

### 1.3 Figma connector batching

- [x] 1.3.1 `fetch_nodes` chunked by `BATCH_SIZE=20`
- [x] 1.3.2 Tests: `tests/test_connector.py`

### 1.4 Incremental sync `file_hashes`

- [x] 1.4.1 `select_files_for_sync` compares per-file content hashes
- [x] 1.4.2 CLI `--regenerate-templates`
- [x] 1.4.3 Tests: updated `tests/test_sync.py`

### 1.5 Design system completeness

- [x] 1.5.1 `RadiusToken` / `ElevationToken` on `DesignTokens`
- [x] 1.5.2 `app_radius.dart.j2`, `app_elevation.dart.j2`

### 1.6 Codegen gates & hygiene

- [x] 1.6.1 `textScaler` hard-fail in `codegen_checks`
- [x] 1.6.2 Fixed width/height hard-fail when `avoid_fixed_sizes`
- [x] 1.6.3 `ParseError` in `build_clean_tree`
- [x] 1.6.4 `logger.exception()` before pipeline rollback
- [x] 1.6.5 Log file → `logs/figma_flutter_agent.log`

### 1.7 Acceptance (§23)

- [x] 1.7.1 E2E fixture → deterministic layout Dart (`tests/test_phase1_production.py`, `tests/test_acceptance.py`)
- [x] 1.7.2 Golden file suite — `tests/fixtures/golden/{onboarding,catalog}/` + `tests/test_golden_generation.py`

### 1.8 Pipeline decomposition

- [x] 1.8.1 `generator/planner.py` — `GenerationPlanContext` + `plan_generation_files()` + `plan_from_figma_root()`
- [x] 1.8.2 `pipeline.py` delegates file planning to planner stage
- [x] 1.8.3 Fetch/parse stages — `stages/fetch.py`, `stages/parse.py` wired in `pipeline.py`
- [x] 1.8.4 Write/snapshot stages — `stages/write.py`, `stages/snapshot.py` wired in `pipeline.py`
- [x] 1.8.5 Asset export stage — `stages/assets.py` wired in `pipeline.py`

### 1.9 Config §11 alignment

- [x] 1.9.1 Nested `theme.generate`, `flutter.architecture`, `state_management.type`, `assets.optimize`
- [x] 1.9.2 Legacy `theme: material_3` coercion
- [x] 1.9.3 `generator/paths.py` — `feature_first` / `layer_first` screen paths
- [x] 1.9.4 State-management stubs (riverpod/bloc/provider) + pubspec deps
- [x] 1.9.5 SVG `optimize_svg()` in asset exporter when `assets.optimize`
- [x] 1.9.6 Tests: `test_config_spec11`, `test_stages`, `test_paths`, `test_optimize`, `test_stages_write_snapshot`
- [x] 1.9.7 Dynamic screen import prefix via `dart_relative_import_prefix()`
- [x] 1.9.8 Codegen checks accept Semantics in `lib/generated/` layout files

### 1.10 Still open (P0/P1)

### 1.10 Semantic typing & a11y

- [x] 1.10.1 Components API semantic typing — `resolve_semantic_node_type()` + layout-frame override
- [x] 1.10.2 Generic `Semantics` wrapper for labeled nodes in layout renderer
- [x] 1.10.3 Golden tests re-enable `validate_generated_dart`

### 1.11 Package imports & state management

- [x] 1.11.1 `ImportContext` + `generation.use_package_imports` config
- [x] 1.11.2 Package imports in screen/widget/layout/main templates
- [x] 1.11.3 Riverpod `ProviderScope` and Provider `ChangeNotifierProvider` in `main.dart`
- [x] 1.11.4 State stub import wired into generated screens
- [x] 1.11.5 Tests: `test_imports.py`, updated renderer/navigation/golden fixtures
- [x] 1.12.1 Cupertino theme variant — `app_cupertino_theme.dart.j2` + `CupertinoApp` bootstrap
- [x] 1.12.2 Bloc `BlocProvider` wiring in `main.dart` + screen bloc import

### 1.13 Phase 1 complete

Phase 1 P0/P1 checklist closed for MVP production path.

**Phase 1 acceptance:** 174 pytest passed, 2 skipped; ruff + mypy green.

---

## Phase 2 — §23 acceptance & semantic polish

### 2.1 Component sets API

- [x] 2.1.1 `FigmaConnector.fetch_component_sets()`
- [x] 2.1.2 Fetch stage loads component sets alongside components
- [x] 2.1.3 Semantic typing resolves component **set** names (e.g. `Button/Primary`)
- [x] 2.1.4 Tests: `test_connector`, `test_components`

### 2.2 Layout semantics

- [x] 2.2.1 `NodeType.CARD` renders as Material `Card` in layout renderer
- [x] 2.2.2 Test: `test_layout_card.py`

### 2.3 §23 acceptance suite

- [x] 2.3.1 `tests/test_acceptance_spec23.py` maps spec §23 criteria to automated checks

**Phase 2 acceptance:** 185 pytest passed, 2 skipped; ruff + mypy green.

---

## Phase 3 — LLM stage & bloc screen wiring

### 3.1 LLM stage extraction

- [x] 3.1.1 `stages/llm.py` with `LlmStageRequest` / `run_llm_stage()`
- [x] 3.1.2 Pipeline delegates primary + destination LLM calls to the stage
- [x] 3.1.3 Tests: `test_stages_llm.py`

### 3.2 Bloc screen-level wiring

- [x] 3.2.1 `state_bloc.dart.j2` emits typed `{{ screen_class }}State`
- [x] 3.2.2 `inject_bloc_builder()` wraps screen `build()` return in `BlocBuilder`
- [x] 3.2.3 Test: `test_render_generation_files_bloc_wraps_screen_with_bloc_builder`

**Phase 3 acceptance:** 189 pytest passed, 2 skipped; ruff + mypy green.

---

## Phase 4 — §23 evaluator & plan/validate stages

### 4.1 Plan/validate stage extraction

- [x] 4.1.1 `stages/plan.py` — `PlanStageRequest` / `plan_generation_output()`
- [x] 4.1.2 `stages/validate.py` — `ValidateStageRequest` / `validate_planned_generation()`
- [x] 4.1.3 Pipeline delegates planning and codegen validation to stages
- [x] 4.1.4 Tests: `test_stages_plan_validate.py`

### 4.2 §23 acceptance evaluator

- [x] 4.2.1 `validation/spec23.py` — `evaluate_spec23()` with 9 criteria
- [x] 4.2.2 `tests/test_acceptance_spec23.py` parametrized over onboarding + catalog fixtures
- [x] 4.2.3 Deterministic MVP path claims §23 for fixture-backed generation

### 4.3 Asset stage tests

- [x] 4.3.1 `tests/test_stages_assets.py` — destination merge + manifest apply

**Phase 4 acceptance:** 189 pytest passed, 2 skipped; ruff + mypy green.

---

## Phase 5 — LLM §23, live smoke & CI

### 5.1 LLM-path §23

- [x] 5.1.1 `evaluate_spec23_llm_path()` + `generation_mode` on `Spec23Report`
- [x] 5.1.2 `llm_response_sample.json` aligned with codegen contract (`textScaler`, `GeneratedScreenShell`)
- [x] 5.1.3 `tests/test_acceptance_spec23_llm.py`

### 5.2 Live Figma smoke

- [x] 5.2.1 `tests/test_live_figma.py` with `@pytest.mark.live_figma`
- [x] 5.2.2 `.env.example` documents `FIGMA_SMOKE_FILE_KEY` / `FIGMA_SMOKE_NODE_ID`

### 5.3 CI & CLI

- [x] 5.3.1 CI: default pytest excludes `live_figma`; dedicated `acceptance` job
- [x] 5.3.2 CI: optional `live-figma` job on `main` push (repository secrets)
- [x] 5.3.3 CLI `figma-flutter validate-spec23` (+ `--llm-fixture`)

**Phase 5 acceptance:** 191 pytest passed, 4 skipped; ruff + mypy green.

---

## Phase 6 — Production P0 (code review 2026-05)

- [x] 6.1 Breakpoints §7.3 (`mobileSmallMax` / `mobileLargeMax` / `tabletMax`)
- [x] 6.2 Theme-aware deterministic layout (`layout_style.py`, `AppSpacing.md`, variants)
- [x] 6.3 §23 `strict=True` evaluator gates
- [x] 6.4 Pipeline `assert` → `FlutterProjectError`
- [x] 6.5 Write stage narrowed exceptions
- [x] 6.6 Config: no silent `.example` fallback
- [x] 6.7 Checklist: `docs/projects/production-readiness-2026-05/checklist.md`

**Phase 6 acceptance:** 199 pytest passed, 4 skipped; ruff + mypy green.

---

## Phase 7 — Constraints, sync tokens, E2E analyze

- [x] 7.1 `layout_positioning` / offsets on clean tree + `Positioned` in STACK
- [x] 7.2 Context-aware `Expanded` / `SizedBox` for FILL sizing
- [x] 7.3 Token-hash aware `select_files_for_sync` (theme refresh)
- [x] 7.4 `tests/test_layout_constraints.py`, `figma_absolute_stack_sample.json`
- [x] 7.5 `tests/test_acceptance_e2e.py` + Flutter in CI acceptance job

**Phase 7 acceptance:** 202 pytest passed, 5 skipped; ruff green.

---

## Phase 8 — Variants, Cupertino, Dev Mode styles

- [x] 8.1 Variant `Size` → `fontSize` in deterministic TEXT
- [x] 8.2 Variant `State=Disabled` → `onPressed: null` / `enabled: false`
- [x] 8.3 `box_decoration_expr` with drop shadows from Dev Mode effects
- [x] 8.4 Cupertino prompts + `CupertinoButton` / `CupertinoTextField` in layout renderer
- [x] 8.5 LLM `theme_variant` threaded through client, stages, destinations

**Phase 8 acceptance:** 207 pytest passed, 5 skipped; ruff + mypy green (2026-05-23).

---

## Phase 9 — Dev Mode gradients in deterministic codegen

- [x] 9.1 `gradient_fill_expr` — linear/radial `BoxDecoration.gradient`
- [x] 9.2 Tests: `tests/test_layout_style_extended.py`

**Phase 9 acceptance:** 209 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 10 — Scroll containers (§7.4 ListView)

- [x] 10.1 `scrollAxis` on clean tree from Figma `overflowDirection`
- [x] 10.2 Deterministic `ListView` / horizontal `ListView` in layout renderer
- [x] 10.3 Tests: `tests/test_layout_scroll.py`, `figma_scroll_vertical_sample.json`

**Phase 10 acceptance:** 214 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 11 — Grid layout (§7.4 GridView)

- [x] 11.1 `NodeType.GRID` from Figma `layoutMode: GRID`
- [x] 11.2 `gridColumnCount`, `gridRowGap`, `gridColumnGap` on clean tree
- [x] 11.3 Deterministic `GridView.count` in layout renderer
- [x] 11.4 Tests: `tests/test_layout_grid.py`, `figma_grid_sample.json`

**Phase 11 acceptance:** 220 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 12 — Component variants §14

- [x] 12.1 `variant_props.py` — Type → Elevated/Outlined/Text/Destructive; Size → padding/font
- [x] 12.2 State → disabled, loading, error; Type Password → `obscureText`
- [x] 12.3 Cupertino filled/plain/destructive from variant Type
- [x] 12.4 Tests: `tests/test_variant_props.py`, extended `test_layout_variants.py`

**Phase 12 acceptance:** 227 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 13 — Form controls §7.4 (Checkbox, Switch)

- [x] 13.1 Semantic types `CHECKBOX`, `SWITCH` from component/layer names
- [x] 13.2 Variant `Checked` / `State` → value + `onChanged`
- [x] 13.3 Material + Cupertino renderers
- [x] 13.4 Tests: `tests/test_layout_form_controls.py`

**Phase 13 acceptance:** 231 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 14 — Tabs & BottomNavigation §7.4

- [x] 14.1 Semantic types `TABS`, `BOTTOM_NAV` (token-aware name matching)
- [x] 14.2 `DefaultTabController` + `TabBar` / `TabBarView`
- [x] 14.3 `BottomNavigationBar` from child labels
- [x] 14.4 Tests: `tests/test_layout_navigation_widgets.py`, `figma_tabs_sample.json`

**Phase 14 acceptance:** 233 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 15 — Radio & Dropdown §7.4

- [x] 15.1 Semantic types `RADIO`, `RADIO_GROUP`, `DROPDOWN`
- [x] 15.2 `RadioListTile` group + `DropdownButton` items from children
- [x] 15.3 Variant selection → `groupValue` / dropdown `value`
- [x] 15.4 Tests: extended `test_layout_form_controls.py`

**Phase 15 acceptance:** 235 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 16 — Dialog & Live Figma CI

- [x] 16.1 Semantic `DIALOG` → `AlertDialog` in deterministic layout
- [x] 16.2 Prototype `OVERLAY` → `showDialog` when destination name is dialog-like
- [x] 16.3 CI `live-figma` job when GitHub secrets are configured
- [x] 16.4 README widget matrix + live smoke docs
- [x] 16.5 Tests: `tests/test_layout_dialog.py`

**Phase 16 acceptance:** 237 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 17 — Slider & BOTH-axis scroll

- [x] 17.1 Semantic `SLIDER` + variant `Value` → `Slider` / `CupertinoSlider`
- [x] 17.2 `overflowDirection: BOTH` → nested `SingleChildScrollView`
- [x] 17.3 Tests: `tests/test_layout_slider.py`, extended `test_layout_scroll.py`

**Phase 17 acceptance:** 241 pytest passed, 5 skipped; golden tests green (2026-05-23).

---

## Phase 18 — Carousel §7.4

- [x] 18.1 Semantic `CAROUSEL` from layer/component names
- [x] 18.2 `PageView` with bounded height from Figma frame size
- [x] 18.3 Tests: `tests/test_layout_carousel.py`, `figma_carousel_sample.json`

**Phase 18 acceptance:** 244 pytest passed, 5 skipped; mypy green (2026-05-23). **§7.4 widget matrix complete** for deterministic path.

---

## Phase 19 — LLM parity & manual acceptance

- [x] 19.1 Extended `llm/prompts.py` with §7.4 semantic types + variant props
- [x] 19.2 `manual-acceptance.md` runbook for demo project QA
- [x] 19.3 Tests: `tests/test_prompts_widgets.py`

**Phase 19 acceptance:** 246 pytest passed, 5 skipped; mypy green (2026-05-23).

---

## Phase 20 — Code review P0 fixes (2026-05)

- [x] 20.1 Carousel → `AspectRatio` + screen-only fixed-size validation (no `GenerationError`)
- [x] 20.2 `Text(..., textScaler: textScaler)` in deterministic layout
- [x] 20.3 `layoutGrow` applies to counter-axis only (parent `layoutMode`)
- [x] 20.4 `figma_carousel_sample.json` in `test_acceptance_spec23`

**Phase 20 acceptance:** 250 pytest passed, 5 skipped; mypy green.

---

## Phase 21 — Lazy scrollables & dual-mode docs (§15)

- [x] 21.1 `ListView.builder` / `GridView.builder` when child count ≥ 8 (`_LAZY_CHILD_THRESHOLD`)
- [x] 21.2 Preserve `shrinkWrap` / `Expanded` behavior for nested and fill-height layouts
- [x] 21.3 Tests: `tests/test_layout_lazy_lists.py`
- [x] 21.4 README + `.ai-figma-flutter.yml.example` — deterministic vs LLM generation modes

**Phase 21 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 22 — Dev Mode docs, classic constraints, bottom nav (2026-05)

- [x] 22.1 `docs/limitations.md` — REST-synthesized styles vs Dev Mode API
- [x] 22.2 Classic `constraints` → `StackPlacement` + `Positioned(left/right/top/bottom)`
- [x] 22.3 Bottom nav: name-based `Icons.*`, `activeIcon`, `currentIndex` from variants
- [x] 22.4 Tests: `figma_constraints_right_bottom_sample.json`, nav/constraint cases

**Phase 22 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 23 — Spec23 strict, RepaintBoundary, a11y auto-fix (§15)

- [x] 23.1 `accessibility.auto_fix` — bump fonts, contrast, derive labels (`apply_accessibility_fixes`)
- [x] 23.2 `RepaintBoundary` on ListView, GridView, PageView, Tabs, BottomNavigationBar
- [x] 23.3 Spec23 strict: `app_theme.dart`, `textScaler`, `flutter_optimization` criterion
- [x] 23.4 Tests: `test_accessibility_fixes.py`, `test_layout_repaint.py`

**Phase 23 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 24 — Stateful bottom nav & manual runbook (2026-05)

- [x] 24.1 `_LayoutBottomNav` StatefulWidget with `setState` on tab tap
- [x] 24.2 `// <custom-code:bottom-nav>` preserved inside `onTap`
- [x] 24.3 Manual runbook: `validate-spec23`, bottom-nav tap, builder lists
- [x] 24.4 Tests updated in `test_layout_navigation_widgets.py`

**Phase 24 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 25 — Automated demo sign-off (offline)

- [x] 25.1 `figma_bottom_nav_sample.json` + `tests/test_demo_signoff.py`
- [x] 25.2 CLI `figma-flutter demo-signoff` (five fixtures, strict §23)
- [x] 25.3 Semantics check: skip nav/tab label `TEXT` children (`codegen_checks.py`)
- [x] 25.4 CI acceptance job includes `test_demo_signoff.py`

**Phase 25 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 26 — Live-check CLI & sign-off matrix (2026-05)

- [x] 26.1 CLI `figma-flutter live-check` (PAT + optional `FIGMA_SMOKE_*` fetch)
- [x] 26.2 Fetch stage logging (`logger.bind` + summary counts)
- [x] 26.3 `docs/projects/production-readiness-2026-05/SIGNOFF.md` gate matrix
- [x] 26.4 `tests/test_cli.py` for `demo-signoff` / `validate-spec23` / `live-check`

**Phase 26 acceptance:** pytest + mypy green (2026-05-23).

---

## Phase 27 — Code review P0/P1 (2026-05)

- [x] 27.1 [production-readiness-review-checklist.md](production-readiness-review-checklist.md) + [spec-amendments.md](../../spec-amendments.md)
- [x] 27.2 Responsive `LayoutBuilder` reflow (root columns, spec §7.3); `max_web_width: 1200`
- [x] 27.3 State templates `// <custom-code>`; `FigmaApiError` sanitization
- [x] 27.4 `quality.enforce_spec9_gates`, `strict_accessibility_labels`, `validation.require_dart_sdk`
- [x] 27.5 Tests: `test_layout_responsive`, `test_errors`, `test_ux_gates`

**Phase 27 acceptance:** 277 pytest passed; mypy green (2026-05-23).

---

## Sprints 0–12 summary

Sprint 0–12 delivered MVP scaffolding (connector, parser, LLM codegen, navigation, sync, validation). Phase 1–5 close critical gaps; **§23 is claimed for deterministic and fixture-backed LLM paths**; live Figma smoke is optional via secrets.
