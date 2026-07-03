# Spec amendments (MVP production interpretation)

Formal deltas vs `docs/spec.md` accepted for **figma-flutter-agent** production signoff until a major version integrates full spec literally.

## §5.1 / §23 — Style metadata (strategy B: REST/CSS synthesis)

**Spec wording:** “Dev Mode data” for inspect-quality style metadata.

**Canonical implementation (strategy B):** Synthesized `cssProperties` and paints from Figma **REST** nodes + Styles API — not the separate Dev Mode API (`docs/limitations.md`).

**Acceptance:** spec23 criterion `rest_css_synthesis` (not “Dev Mode API”). CLI/sign-off report this name explicitly.

**Post-MVP (strategy A):** Optional Dev Mode API / plugin handoff — tracked in `docs/projects/roadmap-10-10.md` only.

## §7.3 — Responsive engine

**Spec:** Breakpoints drive adaptive widget trees (mobile / tablet / desktop).

**Implementation (MVP+):**

- `GeneratedScreenShell` — padding + `contentMaxWidth` via `AppBreakpoints`
- Deterministic `*_layout.dart` — `LayoutBuilder` reflows **root and nested** `Column` frames with 2–4 children to `Row` + `Expanded` on **mobile-large+** (`AppBreakpoints.isWideLayout`, width > 480)
- Root `GridView` uses four-band `crossAxisCount` (mobile-small / mobile-large / tablet / desktop)
- Sidebar adaptive chrome (`_LayoutChromeNav`) - bottom bar (mobile) + `NavigationRail` (tablet/desktop)
- Default `responsive.max_web_width: 1200`

**Breakpoints:** `AppBreakpoints` models spec §7.3 ranges (320–480 compact, 481–768 large mobile, tablet/desktop above 768).

**Mobile bands:** `isMobileSmall` (≤480) keeps stacked `Column` layout; `isMobileLarge` and above use side-by-side reflow and denser grids. Shell padding and `contentMaxWidth` still vary per band via `horizontalPadding` / `contentMaxWidth`.

**Not in scope yet:** breakpoint-specific Figma component sets or wholly separate mobile-band design trees.

## §16–17 — Developer preservation

**Spec:** Bidirectional / per-widget sync (Figma node ↔ Dart widget granularity).

**Implementation:** Region-aware sync — `layout_region_hash` (shell tree with cluster refs) + `cluster_hashes` (per extracted widget) + file hashes; `merge_custom_code` zones; `--no-sync` forces full rewrite; orphan edits blocked via `strict_preservation`.

**Residual gap:** Non-cluster layout edits still rewrite the full `*_layout.dart` file (not per-node Dart regions inside that file). See `docs/limitations.md` (Incremental sync).

## §9 — Code quality bans

**Spec:** Prohibited patterns (deep trees, duplicates).

**Implementation:** `collect_ux_suggestions()` warnings; optional `quality.enforce_spec9_gates: true` raises on excessive depth.

## §19 — IDE integration

**Spec:** Support VS Code, Android Studio, Cursor, and Claude Code workflows.

**Implementation (MVP+):**

- CLI-first workflow: interactive menu (`figma-flutter -i`) from any IDE terminal
- [`.vscode/tasks.json`](../.vscode/tasks.json) — single default build task → interactive menu (DRY)
- [`.vscode/settings.json`](../.vscode/settings.json) — status bar pin via Task Buttons extension
- [`.vscode/launch.json`](../.vscode/launch.json) — debug interactive CLI + Flutter `demo_app`
- [`.vscode/extensions.json`](../.vscode/extensions.json) — recommended Dart/Flutter/Python extensions
- [`docs/ide.md`](ide.md) — runbook for VS Code, Cursor, Android Studio, Claude Code
- [`AGENTS.md`](../AGENTS.md) — Cursor/Codex agent context
- [`CLAUDE.md`](../CLAUDE.md) — Claude Code session workflow
- Developer preservation zones (`// <custom-code>`) editable in any Dart-capable IDE

**Waived (post-MVP):** Marketplace VS Code / Android Studio plugins, Figma URL picker UI, in-IDE diff/sync panels.

## §21.2 — Animation generation

**Spec:** Transitions, micro-animations, and Lottie integration.

**Implementation (MVP):** Prototype link transitions only — parsed from Figma `reactions` / navigation actions and emitted as `PageRouteBuilder`, GoRouter `CustomTransitionPage`, or auto_route `CustomRoute` helpers (`parser/transitions.py`, `generator/templates/prototype_navigation.dart.j2`). `SMART_ANIMATE` maps to a simple scale tween, not shape morphing.

**Waived (post-MVP):** Lottie export, timeline/micro-animation on individual layers, and non-navigation motion. Details: `docs/limitations.md` (Animations).

## §7.6 — Figma Variables

**Spec:** Design tokens sourced from Figma variables (collections, modes).

**Implementation (MVP):** Optional `fetch_variables`; on success, `extract_from_variables` merges into `DesignTokens`. On 403 or missing payload, tokens are derived from node fills and published styles.

**Waived (post-MVP):** Full variables/modes pipeline, alias resolution, and mode-aware theme switching.

## §10 — AI generation mode (default path)

**Spec:** AI agent applies design rules and LLM-driven screen bodies.

**Implementation (MVP production default):** `generation.use_deterministic_screen: true` — rule-based layout engine + templates produce screen/layout Dart. This is the **default production path** for predictable sign-off (`demo-signoff`, spec23 fixtures).

**LLM opt-in:** set `use_deterministic_screen: false` in `.ai-figma-flutter.yml` and configure `anthropic` or `openai` with `require_strict_json_schema: true` (production profile). Dev profile may use other providers with a CLI warning.

## §9 / §23 — Production profile defaults

**Spec:** Production-ready codegen with analyze, preservation, and quality gates.

**Implementation:** `figma-flutter generate` (non-dry-run) applies `apply_production_profile()` unless `--allow-dev-profile`. Gates include `dart analyze` (generated paths only), spec9 depth, strict preservation, WCAG contrast hard fail (`strict_contrast` on the **pre-fix** parse tree; production sets `accessibility.auto_fix: false`), `llm_fallback_to_deterministic: false`, and fail-fast `pub get` / `build_runner` when `routing.type: auto_route`.

**Canonical command:** `figma-flutter generate --figma-url … --project-dir …` (no extra flags).

When amending this file, update `production-readiness-review-checklist.md` and release notes.
