# Known limitations

## Style metadata / “Dev Mode” (§5.1 — strategy B)

The agent does **not** call the separate Figma Dev Mode API. Style metadata is **synthesized from the standard REST file/nodes payload** (canonical acceptance name: **`rest_css_synthesis`**):

- Fills, strokes, effects, and typography on each node
- Published **Styles API** definitions when available (`style_paint_index`)
- Derived `cssProperties` on `NodeStyle` (colors, radius, shadows, gradients) built in `parser/styles.py`

This matches most Dev Mode inspect values for colors and layout CSS, but it is not a 1:1 Dev Mode session export. Gaps to expect:

- No live Dev Mode plugin context or handoff URLs
- Some plugin-only or enterprise-only fields may be absent on REST nodes
- `SCALE` constraints and complex mixed constraints are approximated in codegen

For acceptance, `spec23` criterion `rest_css_synthesis` validates fixture-backed CSS synthesis, not remote Dev Mode API access.

## Classic frame constraints

Deterministic layout maps Figma `constraints.horizontal` / `constraints.vertical` to `Positioned` inside `Stack` parents (`layoutMode: NONE`). `LEFT_RIGHT` / `TOP_BOTTOM` pin both edges; `SCALE` uses width/height when present. Constraints inside Auto Layout parents still rely on flex (`Expanded`, `SizedBox`) unless `layoutPositioning: ABSOLUTE`.

## Bottom navigation state

`BottomNavigationBar` is wrapped in generated `_LayoutBottomNav` (`StatefulWidget`) so tab taps update `currentIndex` via `setState`. Initial index comes from Figma variant metadata. Extend behavior in the `// <custom-code:bottom-nav>` block inside `onTap` (e.g. navigation).

## Figma node types (§7.1)

| Figma type | Parser behavior |
|------------|-----------------|
| `SECTION` | Treated as `FRAME` for Auto Layout inference (column/row/grid) |
| `GROUP` | Explicitly mapped to clean-tree `STACK` (classic `layoutMode: NONE`, `Positioned` children) |
| `FRAME` / `COMPONENT` | Auto Layout → row, column, wrap, grid, or stack |
| Modal layers | `DIALOG` from Figma `overlayPositionType` / `overlayBackground`, published component/set metadata, variant `Type` axes, or layer/component names (last resort for non-instances) |

## Narrow viewport (320px)

Codegen validation (`validate_generated_dart`) rejects layout files that use fixed `width` above 320px (except `Positioned`, `AspectRatio`, scroll views, and `double.infinity`). Column layouts without scroll must use `CrossAxisAlignment.stretch`. This is a static contract, not a Flutter render test.

## LLM structured output and retry

- **Production:** `require_strict_json_schema: true` allows only `anthropic` and `openai` (strict tool/json_schema).
- **Dev:** `openrouter` / `google` use `json_schema` with `strict: false` and log `structured_output_fallback` on client creation and each call.
- Pipeline uses `generate_async()` so retry backoff uses `asyncio.sleep` (HTTP still runs in `asyncio.to_thread`).

## Generation mode (deterministic vs LLM)

**Default:** `generation.use_deterministic_screen: true` — deterministic layout engine and Jinja templates (no LLM call for the screen body). Offline sign-off and CI fixtures use this path.

**LLM:** set `use_deterministic_screen: false` in `.ai-figma-flutter.yml`. Production `generate` requires `anthropic` or `openai` when `require_strict_json_schema: true`. See `docs/spec-amendments.md` §10.

## Figma Variables API

The agent calls `GET /v1/files/:key/variables/local` when available. On **403** (plan/permissions), fetch logs and falls back to paints + published styles for token extraction (`parser/tokens.py`). Full Variables API integration (modes, aliases, collections) is **post-MVP** — see `docs/spec-amendments.md`.

## Corrupt sync snapshot

If `.figma-flutter/snapshot.json` is invalid JSON, the agent quarantines it to `snapshot.json.corrupt` and treats the run as having no prior snapshot (full regen). A warning is appended to pipeline output; production profile sets `sync.fail_on_corrupt_snapshot: true` to fail-fast instead.

## Incremental sync and LLM regeneration (§16–17)

When incremental sync finds **no files to write** and design-tree/token hashes are unchanged, the agent **skips** rewriting `.figma-flutter/snapshot.json` (avoids redundant version bumps).

Incremental sync stores **`layout_region_hash`** (layout shell with cluster subtrees collapsed) and **`cluster_hashes`** (per extracted widget). Edits inside a repeated cluster typically rewrite only `lib/widgets/<widget>.dart`, not `*_layout.dart`. Edits to non-cluster layout structure (spacing, new siblings outside clusters) still rewrite the full layout file — there is no per-line Dart region map inside a single file.

### Policy matrix (LLM mode)

| Tree hash | Tokens | Default behavior | Production profile |
|-----------|--------|------------------|-------------------|
| Changed | any | Full LLM regen | Full LLM regen |
| Unchanged | Unchanged | Skip LLM | Skip LLM |
| Unchanged | Changed | Skip LLM (theme files only) | **Regen LLM** (`regen_llm_on_token_change: true`) |

- When the **design tree hash is unchanged**, the LLM stage is skipped and only theme/token files may update. This is intentional for theme-only sync in dev profiles.
- Use `figma-flutter generate --force-llm-regen` to refresh the LLM screen body after prompt/model changes without editing the Figma frame.
- Destination screens: by default, a failed destination LLM call **fails the run**. Set `generation.allow_destination_stubs: true` or pass `--allow-stubs` to keep placeholder destination screens instead.
- **LLM fallback:** when `use_deterministic_screen: false` and the LLM call fails (API or schema validation), the pipeline can fall back to the deterministic layout engine if `generation.llm_fallback_to_deterministic: true`. Production `generate` (default profile) sets this to `false` (fail-fast). Dev runs: `--allow-dev-profile` restores YAML/default soft behavior.
- **Token-only Figma changes** with an unchanged tree hash skip LLM unless `generation.regen_llm_on_token_change: true` (production default). Use `--force-llm-regen` to refresh the screen body after prompt/model changes.
- Automated policy matrix: `tests/test_llm_incremental_policy.py`.

## Post-generation `dart analyze` (§9 / §23)

| `validation.analyze_scope` | Behavior |
|---------------------------|----------|
| `written_only` | Analyze only files written in the current run (fast incremental) |
| `all_planned` | Analyze the full planned file set (production profile default) |
| `project` | Analyze entire `lib/` tree |

Regex codegen checks remain a fast supplement; production enables `spec23_dart_analyze` with `all_planned`.

## Responsive breakpoints (§7.3)

`lib/theme/app_layout.dart` defines `mobileSmallMax = 480`, `mobileLargeMax = 768`, and `tabletMax = 1024`. Layout reflow uses `AppBreakpoints.isWideLayout` (width > 480) in generated `*_layout.dart` files; side nav uses tablet/desktop only.

## WebP asset export

`assets.webp` defaults to **`false`** in `.ai-figma-flutter.yml`. WebP conversion requires **Pillow** (default dependency); if unavailable, the pipeline warns and keeps PNG assets. Set `assets.webp: true` only when conversion is desired.

## Clean architecture (`layer_first`)

When `flutter.architecture: layer_first`:

- Screens and state stubs use `lib/presentation/screens/` and `lib/presentation/state/`
- Theme, widgets, generated layouts, and assets remain at `lib/theme/`, `lib/widgets/`, `lib/generated/` (not fully layered)

Use `feature_first` (default) unless your Flutter app already follows presentation/domain/data folders and accepts shared widget paths.

## Visual QA (spec §21)

Optional profile `.ai-figma-flutter-visual-qa.yml` enables dark theme, Figma reference PNG export, and golden test scaffolds. Automated pixel-perfect diff against Figma is **not** implemented; golden tests compare Flutter renders. See [visual-qa.md](projects/production-readiness-2026-05/visual-qa.md).

## Animations (spec §21.2 / MVP §22)

**In scope (MVP):** Figma **prototype** navigation transitions only.

| Figma transition | Generated Flutter behavior |
|------------------|----------------------------|
| `DISSOLVE`, `FADE` | Fade (`FadeTransition` / `CustomTransitionPage`) |
| `SLIDE_IN`, `PUSH`, `MOVE_IN`, `SLIDE_OUT`, `MOVE_OUT` | Horizontal slide |
| `SMART_ANIMATE`, `SMART` | Approximated as scale (0.96 → 1), not vector morph |
| `INSTANT` | Zero-duration navigation (no animation curve) |

Implemented in `parser/transitions.py`, `generator/navigation_codegen.py`, and templates `prototype_navigation.dart.j2`, `app_router.dart.j2`, `app_auto_route.dart.j2`. Overlay links (`OVERLAY`) use `showModalBottomSheet` / `showDialog`; `SCROLL_TO` uses scroll helpers.

**Out of scope (post-MVP):** Lottie assets, per-layer micro-animations, Figma variable-driven motion, and pixel-accurate `SMART_ANIMATE` morphing. See `docs/spec-amendments.md` (§21.2).
