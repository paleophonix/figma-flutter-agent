"""Planning, seeding, and syncing subtree widget files."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.subtree.spec import (
    SubtreeWidgetResult,
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse

_LARGE_TRUSTED_SUBTREE_WIDGET_BYTES = 200_000
_MIN_BOTTOM_NAV_BAR_ITEMS = 2
_LAYOUT_WIDGET_REF_RE = re.compile(r"const\s+(\w+Widget\d*)\s*\(")


_BOTTOM_NAV_WIDGET_MARKERS = (
    "BottomNavigationBar(",
    "BottomNavigationBarItem(",
    "_LayoutChromeNav(",
    "_LayoutPillNav(",
    "_LayoutIconNav(",
    "_LayoutBottomNav(",
    "ClipRRect(",
    "BackdropFilter(",
    "borderRadius:",
    "Icons.circle_outlined",
)

_WIDGET_CLASS_DECL_RE = re.compile(r"class\s+(\w+)\s+extends")


def _bottom_nav_widget_needs_refresh(source: str, class_name: str = "") -> bool:
    """True when a cached bottom-nav widget file is stale or placeholder icons."""
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_shrink_only_widget_source,
    )

    declared_name = class_name or "\n".join(_WIDGET_CLASS_DECL_RE.findall(source))
    is_bottom_nav_candidate = "nav" in declared_name.lower() or any(
        marker in source for marker in _BOTTOM_NAV_WIDGET_MARKERS
    )
    if not is_bottom_nav_candidate:
        return False

    if _is_shrink_only_widget_source(source):
        return True
    if "IgnorePointer(ignoring: true" in source and "SizedBox.shrink()" in source:
        return True
    has_figma_chrome = (
        "borderRadius:" in source or "ClipRRect" in source or "BackdropFilter" in source
    )
    if has_figma_chrome:
        if "_LayoutPillNav(" not in source and "_LayoutChromeNav(" in source:
            return True
        if "BottomNavigationBar(" in source:
            return True
        if "FittedBox" in source and "Container(width: 80.0" in source:
            return True
    if source.count("BottomNavigationBarItem(") < _MIN_BOTTOM_NAV_BAR_ITEMS:
        return True
    if source.count("Icons.circle_outlined") >= _MIN_BOTTOM_NAV_BAR_ITEMS:
        return True
    if "_LayoutIconNav(" in source and "required this.slotWidth" not in source:
        return True
    return "constraints.maxHeight > 120.0" not in source


def _media_avatar_widget_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a cached avatar subtree is SVG-only but the tree carries raster photo."""
    from figma_flutter_agent.parser.interaction import find_raster_photo_leaf
    from figma_flutter_agent.schemas import NodeType

    representative = spec.representative

    def _has_structural_image_photo(node: CleanDesignTreeNode, depth: int = 0) -> bool:
        if depth > 5:
            return False
        if node.type == NodeType.IMAGE or node.image_asset_key:
            return True
        return any(_has_structural_image_photo(child, depth=depth + 1) for child in node.children)

    if _has_structural_image_photo(representative) and (
        "Image.asset" not in source or "SizedBox.shrink()" in source
    ):
        return True
    if "SvgPicture" not in source:
        return False
    if find_raster_photo_leaf(representative) is not None:
        return True
    width_match = re.search(r"width:\s*([\d.]+)", source)
    height_match = re.search(r"height:\s*([\d.]+)", source)
    host_width = representative.sizing.width
    host_height = representative.sizing.height
    if width_match and host_width is not None:
        if abs(float(width_match.group(1)) - float(host_width)) > 1.0:
            return True
    if height_match and host_height is not None:
        if abs(float(height_match.group(1)) - float(host_height)) > 1.0:
            return True
    return False


def _icon_badge_glyph_widget_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a cached icon-badge subtree still stretches its glyph to the plate."""
    from figma_flutter_agent.generator.ir.extracted_paint import (
        icon_badge_planned_widget_needs_rematerialization,
    )

    return icon_badge_planned_widget_needs_rematerialization(spec.representative, source)


def _decorative_icon_widget_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a passive tile icon widget still carries back-nav tap chrome."""
    from figma_flutter_agent.parser.interaction import passive_decorative_icon_glyph

    if not passive_decorative_icon_glyph(spec.representative):
        return False
    return "CircleBorder" in source or "back-nav" in source or "InkWell(" in source


def _notification_badge_widget_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a bell+badge host was collapsed to a lone SVG export."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        stack_hosts_notification_badge_overlay,
    )

    if not stack_hosts_notification_badge_overlay(spec.representative):
        return False
    if "Stack(" in source and "Positioned(" in source:
        return False
    return source.count("SvgPicture") >= 1 and "Text(" not in source


def _raster_misrouted_svgpicture_needs_refresh(source: str) -> bool:
    """True when raster assets are emitted through ``SvgPicture.asset``."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        replace_raster_svgpicture_asset_calls,
    )

    return replace_raster_svgpicture_asset_calls(source) != source


def _success_glyph_stack_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a Success/check stack was collapsed to a single raster misroute."""
    root = spec.representative
    name = (root.name or "").strip().lower()
    component = ""
    if root.variant is not None:
        component = (root.variant.component_name or "").strip().lower()
    if name != "success" and component != "success":
        return False
    if _raster_misrouted_svgpicture_needs_refresh(source):
        return True
    if "Image.asset" in source and "Stack(" not in source:
        return True
    return len(root.children) > 1 and "Stack(" not in source


def _trailing_selection_glyph_needs_refresh(source: str, spec: SubtreeWidgetSpec) -> bool:
    """True when a compact trailing check glyph still carries button Ink chrome."""
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_trailing_selection_glyph,
    )

    if not layout_fact_compact_trailing_selection_glyph(spec.representative):
        return False
    return "Ink(" in source or "InkWell(" in source


def _subtree_widget_path_needs_render(
    planned: Mapping[str, str],
    class_name: str,
    *,
    spec: SubtreeWidgetSpec | None = None,
) -> bool:
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
        _is_shrink_only_widget_source,
        preferred_widget_path_for_class,
    )

    preferred = preferred_widget_path_for_class(class_name)
    existing = (planned.get(preferred) or "").strip()
    if not existing:
        return True
    if spec is not None:
        if _media_avatar_widget_needs_refresh(existing, spec):
            return True
        if _decorative_icon_widget_needs_refresh(existing, spec):
            return True
        if _notification_badge_widget_needs_refresh(existing, spec):
            return True
        if _success_glyph_stack_needs_refresh(existing, spec):
            return True
        if _icon_badge_glyph_widget_needs_refresh(existing, spec):
            return True
        if _trailing_selection_glyph_needs_refresh(existing, spec):
            return True
    if _raster_misrouted_svgpicture_needs_refresh(existing):
        return True
    if _bottom_nav_widget_needs_refresh(existing, class_name):
        return True
    if len(existing.encode("utf-8")) > _LARGE_TRUSTED_SUBTREE_WIDGET_BYTES:
        if (
            not _is_shrink_only_widget_source(existing)
            and not _is_self_referential_widget_build(existing, class_name)
            and not _is_foreign_delegate_widget_build(existing, class_name)
        ):
            return False
    if _is_shrink_only_widget_source(existing):
        return True
    if _is_self_referential_widget_build(existing, class_name):
        return True
    return _is_foreign_delegate_widget_build(existing, class_name)


def _collect_subtree_specs_to_render(
    planned: Mapping[str, str],
    specs: Sequence[SubtreeWidgetSpec],
    *,
    layout_class_names: Sequence[str] = (),
    clean_tree: CleanDesignTreeNode | None = None,
) -> list[SubtreeWidgetSpec]:
    """Subtree specs whose planned widget file is missing, shrink-only, or self-referential."""
    to_render: list[SubtreeWidgetSpec] = []
    seen_node_ids: set[str] = set()

    def _maybe_add(spec: SubtreeWidgetSpec) -> None:
        if spec.node_id in seen_node_ids:
            return
        if not _subtree_widget_path_needs_render(planned, spec.class_name, spec=spec):
            return
        seen_node_ids.add(spec.node_id)
        to_render.append(spec)

    for spec in specs:
        _maybe_add(spec)

    if clean_tree is not None:
        for class_name in layout_class_names:
            if not _subtree_widget_path_needs_render(planned, class_name):
                continue
            resolved = _resolve_spec_for_layout_widget_class(
                class_name,
                list(specs),
                clean_tree=clean_tree,
            )
            if resolved is not None:
                _maybe_add(resolved)

    return to_render


def seed_subtree_widgets_from_project(
    planned: dict[str, str],
    *,
    project_dir: Path | None,
    specs: Sequence[SubtreeWidgetSpec],
) -> dict[str, str]:
    """Copy valid on-disk subtree widgets into ``planned`` before re-rendering."""
    if project_dir is None or not project_dir.is_dir() or not specs:
        return planned
    from figma_flutter_agent.generator.planned.reconcile import preferred_widget_path_for_class

    merged = dict(planned)
    for spec in specs:
        if not _subtree_widget_path_needs_render(merged, spec.class_name, spec=spec):
            continue
        rel = preferred_widget_path_for_class(spec.class_name)
        disk = project_dir / rel
        if not disk.is_file():
            continue
        body = disk.read_text(encoding="utf-8")
        if _subtree_widget_path_needs_render({rel: body}, spec.class_name, spec=spec):
            continue
        merged[rel] = body
        logger.info("Seeded subtree widget {} from project disk", spec.class_name)
    return merged


def plan_subtree_widget_files(
    planned: dict[str, str],
    specs: Sequence[SubtreeWidgetSpec],
    *,
    project_dir: Path | None,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> tuple[dict[str, str], SubtreeWidgetResult | None]:
    """Seed widgets from disk when possible; render only missing or broken bodies."""
    if not specs:
        return planned, None
    from figma_flutter_agent.generator.planned.reconcile import (
        preferred_widget_path_for_class,
        repair_foreign_delegate_widget_builds,
        repair_stale_widget_ctor_names_in_planned,
    )
    from figma_flutter_agent.generator.subtree.render import render_subtree_widgets

    merged = repair_foreign_delegate_widget_builds(dict(planned))
    merged = repair_stale_widget_ctor_names_in_planned(merged)
    merged = seed_subtree_widgets_from_project(
        merged,
        project_dir=project_dir,
        specs=specs,
    )
    logger.info("Subtree plan: checking {} widget spec(s)", len(specs))
    layout_names = sorted(_layout_widget_class_names(merged)) if clean_tree is not None else ()
    to_render = _collect_subtree_specs_to_render(
        merged,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    )
    logger.info("Subtree plan: {} widget(s) need render", len(to_render))
    if not to_render:
        files: dict[str, str] = {}
        for spec in specs:
            preferred = preferred_widget_path_for_class(spec.class_name)
            legacy = f"lib/widgets/{spec.file_name}.dart"
            content = merged.get(preferred) or merged.get(legacy)
            if content is not None:
                files[legacy] = content
        return merged, SubtreeWidgetResult(files=files, specs=tuple(specs))

    started = time.monotonic()
    logger.info("Rendering {} subtree widget(s)...", len(to_render))
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        project_dir=project_dir,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    logger.info(
        "Subtree widgets rendered in {:.1f}s ({} skipped as already valid)",
        time.monotonic() - started,
        len(specs) - len(to_render),
    )
    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        content = subtree.files.get(legacy_path)
        if content is not None:
            merged[preferred_widget_path_for_class(spec.class_name)] = content
    return merged, subtree


def ensure_subtree_widget_planned_files(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> dict[str, str]:
    """Render missing ``lib/widgets`` files required by layout ``extracted_widget_ref`` stubs."""
    from figma_flutter_agent.generator.subtree.render import render_subtree_widgets

    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return planned
    merged = dict(planned)
    to_render = _collect_subtree_specs_to_render(merged, specs)
    if not to_render:
        return merged
    started = time.monotonic()
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
    )
    from figma_flutter_agent.generator.planned.reconcile import preferred_widget_path_for_class

    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        content = subtree.files.get(legacy_path)
        if content is None:
            continue
        merged[preferred_widget_path_for_class(spec.class_name)] = content
    logger.info(
        "Rendered {} missing subtree widget(s) in {:.1f}s ({} already present)",
        len(to_render),
        time.monotonic() - started,
        len(specs) - len(to_render),
    )
    return merged


def _layout_widget_class_names(planned: Mapping[str, str]) -> set[str]:
    names: set[str] = set()
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith("_layout.dart"):
            continue
        names.update(_LAYOUT_WIDGET_REF_RE.findall(content))
    return names


def _resolve_spec_for_layout_widget_class(
    class_name: str,
    specs: Sequence[SubtreeWidgetSpec],
    *,
    clean_tree: CleanDesignTreeNode,
) -> SubtreeWidgetSpec | None:
    from figma_flutter_agent.generator.layout.common import to_snake_case
    from figma_flutter_agent.generator.planned.reconcile import _normalized_widget_stem
    from figma_flutter_agent.generator.subtree.merge import _collect_all_nodes

    direct = next((spec for spec in specs if spec.class_name == class_name), None)
    if direct is not None:
        return direct

    ref_node_ids = {
        node.id
        for node in _collect_all_nodes(clean_tree)
        if (node.extracted_widget_ref or "").strip() == class_name
    }
    if ref_node_ids:
        matched = next((spec for spec in specs if spec.node_id in ref_node_ids), None)
        if matched is not None:
            return matched

    target_stem = _normalized_widget_stem(to_snake_case(class_name))
    stem_matches = [
        spec
        for spec in specs
        if _normalized_widget_stem(to_snake_case(spec.class_name)) == target_stem
    ]
    if len(stem_matches) == 1:
        spec = stem_matches[0]
        if spec.class_name == class_name:
            return spec
        return SubtreeWidgetSpec(
            node_id=spec.node_id,
            class_name=class_name,
            file_name=to_snake_case(class_name),
            representative=spec.representative,
            vector_count=spec.vector_count,
        )

    base = re.sub(r"\d+$", "", class_name)
    if not base:
        return None
    prefix_matches = [spec for spec in specs if spec.class_name.startswith(base)]
    if len(prefix_matches) != 1:
        return None
    spec = prefix_matches[0]
    if spec.class_name == class_name:
        return spec
    return SubtreeWidgetSpec(
        node_id=spec.node_id,
        class_name=class_name,
        file_name=to_snake_case(class_name),
        representative=spec.representative,
        vector_count=spec.vector_count,
    )


def preserve_deterministic_widget_planned_files(
    planned: dict[str, str],
    baseline: dict[str, str],
) -> dict[str, str]:
    """Keep ``lib/widgets/*.dart`` from an earlier plan pass after IR re-plan drops them."""
    merged = dict(planned)
    for path, content in baseline.items():
        key = path.replace("\\", "/")
        if key.startswith("lib/widgets/") and key.endswith(".dart") and key not in merged:
            merged[key] = content
    return merged


def sync_subtree_extracted_widgets(
    generation: FlutterGenerationResponse,
    *,
    clean_tree: CleanDesignTreeNode,
    planned_files: dict[str, str],
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> tuple[FlutterGenerationResponse, dict[str, str], bool]:
    """Ensure deterministic subtree widget files and ``extractedWidgets`` entries exist."""
    from figma_flutter_agent.generator.subtree.render import render_subtree_widgets
    from figma_flutter_agent.schemas import ExtractedWidget

    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return generation, planned_files, False

    subtree = render_subtree_widgets(
        specs,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
    )
    merged_planned = dict(planned_files)
    changed = False
    for path, content in subtree.files.items():
        key = path.replace("\\", "/")
        if merged_planned.get(key) != content:
            merged_planned[key] = content
            changed = True

    by_name = {widget.widget_name: widget for widget in generation.extracted_widgets}
    widgets = list(generation.extracted_widgets)
    for spec in specs:
        path = f"lib/widgets/{spec.file_name}.dart"
        code = subtree.files.get(path)
        if not code:
            continue
        existing = by_name.get(spec.class_name)
        if existing is None:
            widgets.append(
                ExtractedWidget(
                    widget_name=spec.class_name,
                    code=code,
                ),
            )
            changed = True
            continue
        if not existing.resolved_code():
            idx = widgets.index(existing)
            widgets[idx] = existing.model_copy(update={"code": code})
            changed = True

    if not changed:
        return generation, merged_planned, False
    return generation.model_copy(update={"extracted_widgets": widgets}), merged_planned, True
