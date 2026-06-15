# generator

## Purpose

Render Dart files from Jinja templates, merge custom code, update pubspec, and validate output.

Writes are **transactional**: `DartWriter.write_files()` and `update_pubspec()` stage changes; `validate_dart_project()` runs before `commit_batch()` / `commit_pubspec_batch()`. On failure, call `rollback_batch()` to restore files and pubspec.

## Example

```python
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project
from figma_flutter_agent.generator.writing.core import DartWriter

files = DartRenderer().render_generation_files(generation, feature_name="home", uses_svg=True)
writer = DartWriter(project_dir)
batch = writer.write_files(files)
pubspec_batch = update_pubspec(project_dir, ["assets/icons/"], needs_svg=True)
validate_dart_project(
    project_dir,
    analyze_scope="generated_only",
    relative_paths=sorted(planned.keys()),
)
writer.commit_batch(batch)
commit_pubspec_batch(pubspec_batch)
```

Call `validate_generated_dart()` before writing files to enforce Semantics/textScaler contracts from all screen clean trees (primary + prototype destinations). When overlay prototype links exist, `lib/core/prototype_navigation.dart` provides `showModalBottomSheet` or `showDialog` helpers (dialog-like destination frame names). SCROLL_TO links generate `prototype_scroll_targets.dart` plus scroll helpers in `prototype_navigation.dart`. GoRouter routes with prototype transitions use `CustomTransitionPage` in `app_router.dart`.

For `auto_route`, the pipeline runs `pub get` and `build_runner` before `flutter analyze`. Prototype transitions map to `CustomRoute` the same way as GoRouter `CustomTransitionPage`. Enable optional dark theme via `dark_mode.enabled` in config to emit `AppTheme.dark()`. The pipeline also generates `lib/main.dart` wired to theme and the configured router.

## LLM Context

Embed `screen_code` inside `screen.dart.j2`; widget bodies go to `lib/widgets/{snake_name}.dart`. Screen templates auto-import extracted widgets; widget templates import `AppColors`, `AppSpacing`, and `flutter_svg` when needed. Preserve `// <custom-code>` blocks when regenerating.

In LLM mode, `subtree_widgets.py` renders vector-rich direct-child subtrees as deterministic widgets, passes stackPlacement hints to the LLM, then `reconcile_llm_screen_with_subtrees()` forces `const WidgetName()` at those coordinates (replacing abbreviated inline SVG stacks). Compact multicolor icon stacks (e.g. Google G, 2–12 vectors, ≤64×64) are collected with screen-absolute placement; labeled social-login stacks are excluded from separate subtree extraction so icons stay inside the row widget. Layout/syntax fixes run through the AST sidecar in `planned_dart.reconcile_planned_dart_files`, not regex splicing of `render_node_body` into `screenCode`. `background/` hoists decorative root vectors into a `Positioned.fill` + `FittedBox(BoxFit.cover)` layer behind the centered design canvas so ambient art does not drift on wide viewports.

Deterministic layout lives under [`layout/`](layout/) (`widget.py`, `renderer.py`, `common.py`, …). Dart postprocess and syntax repairs live under [`dart/`](dart/). Geometry planner and invariants under [`geometry/`](geometry/). Screen IR under [`ir/`](ir/).

Deterministic layout is split across modules in `layout/`: `widget.py` (per-node dispatch), `renderer.py` (layout/screen file assembly), `cupertino.py` (Cupertino shells and tap targets), `responsive.py` (breakpoints), `scroll.py` (ListView/GridView), `navigation.py` (tabs, carousel, bottom nav), and `common.py` (shared helpers). Cluster widgets are rendered with the full `cluster_classes` map so nested clusters (e.g. `TitleWidget` inside `ProductCardWidget`) emit `const` references.

Set `theme.variant: cupertino` in project YAML for iOS-style controls. Coverage per node type is documented in [docs/cupertino-coverage.md](../../../docs/cupertino-coverage.md) at the repo root.

## Screen IR validation

`ir_validate.apply_ir_guards()` mutates the clean tree / IR overrides (stack z-order align, nested scroll, row flex, touch target, keyboard scroll, token snap). `validate_screen_ir(..., apply_guards=True)` runs guards, then `sanitize_screen_ir_llm_drift()` (omit/state/adaptiveRules/extracted/phantom/duplicate cleanup), a second child-realign pass, then read-only checks; set `apply_guards=False` to validate LLM output without guard auto-fixes (sanitizers still run). Unregistered token overrides in the guard path are dropped with a warning instead of aborting. Fail-closed: wrong `screenIr.root`, IR cycles, duplicate ids after sanitize, missing on-disk assets, stack ghost occlusion, geometry hard invariants. `IrEmitPolicy` on `IrEmitContext` toggles guard/validate passes before `ir_emitter` materializes Dart. Parse-time stack backdrop ordering lives in `parser/stack_paint.py` (`build_clean_tree`). Repair with `use_screen_ir` scopes targets to `screenIr` + `irPatches` (not `screenCode` diffs); `reconcile_planned_dart_files(ast_full_reconcile_paths=...)` limits AST sidecar to touched planned paths after repair.

Deterministic layout uses `variant_props.py` to map Figma `componentProperties` (Type/State/Size) to Material or Cupertino controls depending on `theme.variant`. Frames named like `Profile Tabs`, `Main Bottom Nav`, or `Hero Carousel` render tab scaffolds, adaptive `_LayoutChromeNav` (`CupertinoTabBar` or `BottomNavigationBar` on mobile, `NavigationRail` on wide breakpoints), or `PageView` respectively. Classic frame `constraints` on `Stack` parents map to `Positioned` edge pins.
