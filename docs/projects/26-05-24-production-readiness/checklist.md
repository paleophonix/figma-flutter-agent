# Production readiness checklist

Tracked from code review 2026-05. See `docs/projects/code-review-2026-05/plan.md` for sprint history.

## Must-fix (P0)

- [x] **Breakpoints §7.3** — `AppBreakpoints` mobile 320–480 / 481–768, tablet 769–1024, desktop 1025+
- [x] **Deterministic renderer** — `AppSpacing`, `AppElevation`, variant `enabled`, layout theme imports
- [x] **§23 evaluator hardening** — `strict=True` mode with substantive checks
- [x] **`assert` in pipeline** → `FlutterProjectError`
- [x] **Write stage** — narrow exception handling
- [x] **Config fallback** — `.example` only when explicitly requested
- [x] **Component variants §14** — Type/State/Size → button style, disabled/loading, password, error decoration
- [x] **§23 + dart analyze** in CI acceptance job (Flutter SDK)

## Should-fix (P1)

- [x] **Constraints** — context `Expanded` / `Positioned` for STACK
- [x] **Token hashes** in `select_files_for_sync`
- [x] **Cupertino vs LLM prompt alignment** — theme-specific prompts + Cupertino layout controls
- [x] **Default generation mode** — documented in `.ai-figma-flutter.yml.example`
- [x] **Dev Mode gradients** — `gradient_fill_expr` in deterministic `BoxDecoration`
- [x] **Scroll frames §7.4** — `overflowDirection` → `ListView` in deterministic renderer
- [x] **Grid frames §7.4** — `layoutMode: GRID` → `GridView.count`
- [x] **Form controls §7.4** — Checkbox / Switch / Radio / Dropdown + variants
- [x] **Navigation §7.4** — Tabs (`DefaultTabController`) + BottomNavigationBar
- [x] **Dialog §7.4** — `AlertDialog` + prototype `showDialog` for dialog destinations
- [x] **Slider §7.4** — `Slider` / `CupertinoSlider` + variant `Value`
- [x] **BOTH overflow** — nested `SingleChildScrollView` (vertical + horizontal)
- [x] **Carousel §7.4** — `PageView` for carousel/pager/swiper frames
- [x] **Lazy lists §15** — `ListView.builder` / `GridView.builder` when ≥ 8 children
- [x] **Dev Mode scope** — documented REST synthesis in `docs/limitations.md`
- [x] **Classic constraints** — `RIGHT`/`BOTTOM`/`LEFT_RIGHT` → `Positioned` pins
- [x] **Bottom nav icons** — name-based icons + variant-driven `currentIndex`
- [x] **RepaintBoundary §15** — scrollable and heavy widgets wrapped in layout codegen
- [x] **Accessibility auto-fix** — `accessibility.auto_fix` in config + pipeline
- [x] **Spec23 strict+** — `flutter_optimization`, theme/textScaler gates

## Manual QA

- [x] **Runbook** — `docs/projects/production-readiness-2026-05/manual-acceptance.md`
- [x] **Offline demo sign-off** — `figma-flutter demo-signoff` + `tests/test_demo_signoff.py`
- [x] **Live credential CLI** — `figma-flutter live-check` (+ `--dump` for `.debug`)
- [ ] **Live demo sign-off** — execute runbook §2–8 on a real Figma frame + `demo_app`
- [x] **Stateful bottom nav** — `_LayoutBottomNav` with working tab selection

## LLM parity

- [x] **Prompts §7.4** — semantic types and variant props in `llm/prompts.py`

## Tests & CI

- [x] Breakpoints regression tests
- [x] Variant disabled → `onPressed: null` test
- [x] E2E: fixture → `flutter analyze` (`test_acceptance_e2e.py`)
- [x] Live Figma gate on secrets (CI job `live-figma`; step skips when secrets unset)
