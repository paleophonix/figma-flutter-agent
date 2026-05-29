# generator

## Purpose

Render Dart files from Jinja templates, merge custom code, update pubspec, and validate output.

Writes are **transactional**: `DartWriter.write_files()` and `update_pubspec()` stage changes; `validate_dart_project()` runs before `commit_batch()` / `commit_pubspec_batch()`. On failure, call `rollback_batch()` to restore files and pubspec.

## Example

```python
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.validation import validate_dart_project
from figma_flutter_agent.generator.writer import DartWriter

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

In LLM mode, `subtree_widgets.py` renders vector-rich direct-child subtrees as deterministic widgets, passes stackPlacement hints to the LLM, then `reconcile_llm_screen_with_subtrees()` forces `const WidgetName()` at those coordinates (replacing abbreviated inline SVG stacks). Compact multicolor icon stacks (e.g. Google G, 2–12 vectors, ≤64×64) are collected with screen-absolute placement; labeled social-login stacks are excluded from separate subtree extraction so icons stay inside the row widget. Layout/syntax fixes run through the AST sidecar in `planned_dart.reconcile_planned_dart_files`, not regex splicing of `render_node_body` into `screenCode`. `ambient_background.py` hoists decorative root vectors into a `Positioned.fill` + `FittedBox(BoxFit.cover)` layer behind the centered design canvas so ambient art does not drift on wide viewports.

Deterministic layout is split across modules: `layout_widget.py` (per-node dispatch), `layout_renderer.py` (layout/screen file assembly), `layout_responsive.py` (breakpoints), `layout_scroll.py` (ListView/GridView), `layout_navigation.py` (tabs, carousel, bottom nav), and `layout_common.py` (shared helpers). Cluster widgets are rendered with the full `cluster_classes` map so nested clusters (e.g. `TitleWidget` inside `ProductCardWidget`) emit `const` references.

## Screen IR validation

`ir_validate.validate_screen_ir()` runs before `ir_emitter` materializes Dart. It checks IR against the clean tree, may **mutate** the tree (nested scroll flags, row text flex wrap, min touch target, keyboard scroll on nearest `COLUMN`), and raises `GenerationError` on hard failures (duplicate `figmaId`, ghost stack occlusion, contrast, missing assets when `project_dir` is set). Pass `tokens=DesignTokens` to enforce palette/typography on IR `overrides`. LLM paths pass `project_dir` and `tokens` from `llm/client.py` and pipeline stages.

Deterministic layout uses `variant_props.py` to map Figma `componentProperties` (Type/State/Size) to `ElevatedButton`/`OutlinedButton`/`TextButton`, `Checkbox`/`Switch`/`RadioListTile`/`DropdownButton`, `obscureText`, and error `InputDecoration`. Frames named like `Profile Tabs`, `Main Bottom Nav`, or `Hero Carousel` render `DefaultTabController`, adaptive `_LayoutChromeNav` (bottom bar on mobile, `NavigationRail` on tablet/desktop), or `PageView` respectively. Classic frame `constraints` on `Stack` parents map to `Positioned` edge pins.
