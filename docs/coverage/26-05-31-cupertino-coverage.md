# Cupertino theme coverage (spec §3)

Set `theme.variant: cupertino` in `.ai-figma-flutter.yml` to target iOS-style output. The agent still imports `package:flutter/material.dart` in generated layout files because shared primitives (`Colors`, `BorderRadius`, `GestureDetector`, semantics) live there; Cupertino controls come from `package:flutter/cupertino.dart`.

## Coverage matrix

| Area | `material_3` | `cupertino` | Module |
|------|--------------|-------------|--------|
| App bootstrap | `MaterialApp` + `AppTheme` | `CupertinoApp` + `AppCupertinoTheme` | `main.dart.j2`, `renderer_theme.py` |
| LLM system prompts | Material L3–L5 | Cupertino L3–L5 | `llm/prompts.py` |
| Screen shell (when `use_scaffold`) | `Scaffold` + `AppBar` | `CupertinoPageScaffold` + `CupertinoNavigationBar` | `layout_cupertino.py`, `layout_renderer.py`, `ir_emitter.py` |
| Classic full-bleed frame (`STACK` root) | `Material` background | `CupertinoPageScaffold` + `SafeArea` | `layout_cupertino.py` |
| BUTTON (leaf) | Material buttons | `CupertinoButton` / `.filled` | `layout_form.py`, `variant_props.py` |
| BUTTON (composite stack) | `Material` + `InkWell` | `GestureDetector` + optional `ClipRRect` | `layout_cupertino.py` |
| INPUT | `TextField` | `CupertinoTextField` | `layout_form.py` |
| CHECKBOX / SWITCH / SLIDER | Material controls | Cupertino equivalents | `variant_props.py` |
| RADIO / RADIO_GROUP | `RadioListTile` | `CupertinoRadio` rows | `variant_props.py` |
| DROPDOWN | `DropdownButton` | `CupertinoPicker` (bounded) | `variant_props.py` |
| DIALOG | `AlertDialog` | `CupertinoAlertDialog` | `variant_props.py` |
| TABS | `DefaultTabController` + `TabBar` | `CupertinoTabScaffold` + `CupertinoTabBar` | `layout_navigation.py` |
| BOTTOM_NAV (mobile) | `BottomNavigationBar` | `CupertinoTabBar` | `layout_navigation.py` |
| BOTTOM_NAV (tablet/desktop) | `NavigationRail` | `NavigationRail` (Material; adaptive chrome) | `layout_navigation.py` |
| CAROUSEL | `PageView` | `PageView` (shared) | `layout_navigation.py` |
| CARD | `Card` | `Card` (Material container; no Cupertino analogue) | `layout_widget.py` |
| Cluster / subtree widgets | theme-agnostic Dart | same | `layout_widget.py` |
| AST sidecar / syntax repair | shared | shared | `planned_dart.py`, `dart_syntax_repairs.py` |

## Intentional hybrid (Material alongside Cupertino)

- **Navigation rail** on wide breakpoints stays Material (`NavigationRail`) because Flutter has no Cupertino rail; tab labels reuse `BottomNavigationBarItem` with `Icon` / `SvgPicture` assets.
- **Generated layout** keeps `material.dart` for geometry, colors, and `RepaintBoundary`; this is normal for Cupertino apps.
- **LLM `screenCode`** may mix widgets if the model drifts; deterministic `lib/generated/*_layout.dart` follows the table above.

## Configuration

```yaml
theme:
  variant: cupertino  # material_3 | cupertino
  generate: true
```

`layout.use_scaffold: true` with a non-`STACK` root enables the navigation bar shell. Classic Figma absolute frames (`STACK` screen roots) stay full-bleed and use `CupertinoPageScaffold` inside the layout class instead.

## Verification

```bash
poetry run pytest tests/test_layout_cupertino.py tests/test_layout_form_controls.py tests/test_cupertino_navigation.py -q
```

Manual: set `theme.variant: cupertino`, run `figma-flutter generate`, confirm `CupertinoApp` in `lib/main.dart` and Cupertino controls in `lib/generated/*_layout.dart`.

## Future work (P2)

- `Card` → bordered `Container` styled from tokens when `cupertino`.
- Cupertino modal sheets for prototype `showModalBottomSheet` destinations.
- Golden PNG baselines per theme variant.
