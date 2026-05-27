"""Deterministic widgets for vector-rich screen subtrees in LLM generation mode."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.layout_renderer import render_node_body, render_widget_file
from figma_flutter_agent.generator.renderer import to_pascal_case, to_snake_case
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MIN_VECTOR_NODES = 8
_MIN_SUBTREE_AREA = 12_000.0
_MIN_COMPACT_ICON_VECTORS = 2
_MAX_COMPACT_ICON_VECTORS = 12
_MAX_COMPACT_ICON_WIDTH = 64.0
_MAX_COMPACT_ICON_HEIGHT = 64.0
_SOCIAL_BUTTON_LABELS = ("CONTINUE WITH FACEBOOK", "CONTINUE WITH GOOGLE")
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.TEXT,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
    }
)
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
_SVG_ASSET_PATH_RE = re.compile(r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_IMAGE_ASSET_PATH_RE = re.compile(r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_POSITIONED_CALL_RE = re.compile(r"(?<![A-Za-z0-9_])Positioned\(")
_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+\w+\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)


@dataclass(frozen=True)
class SubtreeWidgetSpec:
    """Metadata for a deterministic subtree-backed widget."""

    node_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode
    vector_count: int


@dataclass(frozen=True)
class SubtreeWidgetResult:
    """Generated subtree widget files."""

    files: dict[str, str]
    specs: tuple[SubtreeWidgetSpec, ...]


def _count_vector_nodes(node: CleanDesignTreeNode) -> int:
    total = 0
    if node.type in {NodeType.VECTOR, NodeType.IMAGE} or node.vector_asset_key or node.image_asset_key:
        total += 1
    for child in node.children:
        total += _count_vector_nodes(child)
    return total


def _count_interactive_nodes(node: CleanDesignTreeNode) -> int:
    total = 1 if node.type in _INTERACTIVE_TYPES else 0
    for child in node.children:
        total += _count_interactive_nodes(child)
    return total


def _subtree_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return width * height


def _subtree_class_name(node: CleanDesignTreeNode, widget_suffix: str) -> str:
    base = to_pascal_case(node.name) or f"Subtree{node.id.replace(':', '')}"
    if base.endswith(widget_suffix):
        return base
    return f"{base}{widget_suffix}"


def _is_subtree_candidate(node: CleanDesignTreeNode, *, is_direct_child: bool = False) -> bool:
    vector_count = _count_vector_nodes(node)
    min_vectors = 6 if is_direct_child else _MIN_VECTOR_NODES
    if vector_count < min_vectors:
        return False
    if not is_direct_child and _subtree_area(node) < _MIN_SUBTREE_AREA:
        return False
    interactive_count = _count_interactive_nodes(node)
    return vector_count > interactive_count


def _is_compact_icon_subtree(node: CleanDesignTreeNode) -> bool:
    """Detect small multicolor icon stacks (e.g. Google G) that LLMs often break."""
    if node.type != NodeType.STACK:
        return False
    vector_count = _count_vector_nodes(node)
    if vector_count < _MIN_COMPACT_ICON_VECTORS or vector_count > _MAX_COMPACT_ICON_VECTORS:
        return False
    placement = node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return False
    if placement.width > _MAX_COMPACT_ICON_WIDTH or placement.height > _MAX_COMPACT_ICON_HEIGHT:
        return False
    return _count_interactive_nodes(node) < vector_count


def _with_screen_stack_placement(
    node: CleanDesignTreeNode,
    *,
    screen_left: float,
    screen_top: float,
) -> CleanDesignTreeNode:
    placement = node.stack_placement
    if placement is None:
        return node
    return node.model_copy(
        update={
            "stack_placement": placement.model_copy(
                update={"left": screen_left, "top": screen_top},
            ),
        },
    )


def _append_subtree_spec(
    specs: list[SubtreeWidgetSpec],
    *,
    node: CleanDesignTreeNode,
    widget_suffix: str,
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    screen_left: float | None = None,
    screen_top: float | None = None,
) -> None:
    if node.id in used_node_ids:
        return
    representative = node
    if screen_left is not None and screen_top is not None:
        representative = _with_screen_stack_placement(
            node,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    base_class_name = _subtree_class_name(node, widget_suffix)
    class_name = base_class_name
    file_name = to_snake_case(class_name)
    suffix = 2
    while file_name in used_file_names or class_name in used_class_names:
        class_name = f"{base_class_name}{suffix}"
        file_name = f"{to_snake_case(base_class_name)}_{suffix}"
        suffix += 1
    used_file_names.add(file_name)
    used_class_names.add(class_name)
    used_node_ids.add(node.id)
    specs.append(
        SubtreeWidgetSpec(
            node_id=node.id,
            class_name=class_name,
            file_name=file_name,
            representative=representative,
            vector_count=_count_vector_nodes(node),
        )
    )


def _social_button_subtree_ids(root: CleanDesignTreeNode) -> frozenset[str]:
    """Node ids inside labeled social login button stacks (icons belong in the row)."""
    ids: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        ids.add(node.id)
        for child in node.children:
            walk(child)

    for _label, stack in _collect_labeled_social_button_stacks(root):
        walk(stack)
    return frozenset(ids)


def _walk_compact_icon_subtrees(
    node: CleanDesignTreeNode,
    *,
    offset_left: float,
    offset_top: float,
    widget_suffix: str,
    specs: list[SubtreeWidgetSpec],
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    excluded_node_ids: frozenset[str],
) -> None:
    if node.id in excluded_node_ids:
        return
    placement = node.stack_placement
    screen_left = offset_left + (placement.left if placement is not None else 0.0)
    screen_top = offset_top + (placement.top if placement is not None else 0.0)
    if _is_compact_icon_subtree(node):
        _append_subtree_spec(
            specs,
            node=node,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    for child in node.children:
        _walk_compact_icon_subtrees(
            child,
            offset_left=screen_left,
            offset_top=screen_top,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded_node_ids,
        )


def collect_subtree_widget_specs(
    root: CleanDesignTreeNode,
    *,
    widget_suffix: str,
    reserved_file_names: set[str] | None = None,
) -> list[SubtreeWidgetSpec]:
    """Collect vector-rich direct child subtrees that should not be simplified by the LLM."""
    reserved = reserved_file_names or set()
    specs: list[SubtreeWidgetSpec] = []
    used_file_names = set(reserved)
    used_class_names: set[str] = set()
    used_node_ids: set[str] = set()

    for child in root.children:
        if _social_button_label_in_subtree(child):
            continue
        if not _is_subtree_candidate(child, is_direct_child=True):
            continue
        _append_subtree_spec(
            specs,
            node=child,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
        )

    excluded = _social_button_subtree_ids(root)
    for child in root.children:
        if _social_button_label_in_subtree(child):
            continue
        _walk_compact_icon_subtrees(
            child,
            offset_left=0.0,
            offset_top=0.0,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded,
        )
    social_ids = _social_button_subtree_ids(root)
    return [spec for spec in specs if spec.node_id not in social_ids]


def render_subtree_widgets(
    specs: list[SubtreeWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> SubtreeWidgetResult:
    """Render deterministic widget files for vector-rich subtrees."""
    files: dict[str, str] = {}
    for spec in specs:
        body = render_node_body(spec.representative, uses_svg=uses_svg)
        path = f"lib/widgets/{spec.file_name}.dart"
        files[path] = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=path,
        )
    return SubtreeWidgetResult(files=files, specs=tuple(specs))


def build_subtree_widget_hints(specs: list[SubtreeWidgetSpec]) -> list[str]:
    """Build LLM hints for pre-rendered subtree widgets."""
    hints: list[str] = []
    for spec in specs:
        placement = spec.representative.stack_placement
        placement_hint = ""
        if (
            placement is not None
            and placement.width is not None
            and placement.height is not None
        ):
            placement_hint = (
                f" Place exactly one Positioned(left: {placement.left}, top: {placement.top}, "
                f"width: {placement.width}, height: {placement.height}, "
                f"child: const {spec.class_name}()) in screenCode."
            )
        hints.append(
            f"Prebuilt vector-rich subtree widget '{spec.class_name}' "
            f"(node {spec.node_id}, {spec.vector_count} vectors) is already generated at "
            f"lib/widgets/{spec.file_name}.dart.{placement_hint} "
            f"Use only `const {spec.class_name}()` for this subtree — do NOT inline SvgPicture "
            "stacks, abbreviate vector layers, or duplicate the subtree in extractedWidgets."
        )
    return hints


def _extract_asset_paths(source: str) -> frozenset[str]:
    paths = {match.group("path") for match in _SVG_ASSET_PATH_RE.finditer(source)}
    paths.update(match.group("path") for match in _IMAGE_ASSET_PATH_RE.finditer(source))
    return frozenset(paths)


def _extract_widget_class_name(source: str) -> str | None:
    match = _WIDGET_CLASS_RE.search(source)
    if match is None:
        return None
    return match.group("name")


def _rename_widget_class(source: str, old_class: str, new_class: str) -> str:
    if old_class == new_class:
        return source
    return re.sub(rf"\b{re.escape(old_class)}\b", new_class, source)


def _collect_widget_class_names(
    planned_files: dict[str, str],
    *,
    exclude_paths: frozenset[str] | None = None,
) -> set[str]:
    excluded = exclude_paths or frozenset()
    names: set[str] = set()
    for path, content in planned_files.items():
        if path in excluded:
            continue
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        if class_name is not None:
            names.add(class_name)
    return names


def _resolve_merged_widget_class_name(
    *,
    llm_class: str,
    subtree_class: str,
    spec_class: str | None,
    used_class_names: set[str],
) -> str:
    for candidate in (llm_class, spec_class or "", subtree_class):
        if candidate and candidate not in used_class_names:
            return candidate
    base = spec_class or llm_class or subtree_class
    suffix = 2
    while f"{base}{suffix}" in used_class_names:
        suffix += 1
    return f"{base}{suffix}"


def merge_thin_llm_widgets_with_subtrees(
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult,
) -> dict[str, str]:
    """Replace under-specified LLM extracted widgets with deterministic subtree bodies."""
    if not subtree_result.files:
        return planned_files

    updated = dict(planned_files)
    spec_by_path = {f"lib/widgets/{spec.file_name}.dart": spec for spec in subtree_result.specs}
    subtree_assets = {
        path: _extract_asset_paths(content) for path, content in subtree_result.files.items()
    }

    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    for path, llm_content in list(updated.items()):
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue

        llm_assets = _extract_asset_paths(llm_content)
        llm_syntax_broken = validate_dart_delimiters(llm_content) is not None
        if not llm_assets:
            continue

        best_path: str | None = None
        best_score = 0.0
        best_assets: frozenset[str] = frozenset()
        for subtree_path, assets in subtree_assets.items():
            if not assets:
                continue
            overlap = len(llm_assets & assets)
            if overlap == 0:
                continue
            score = overlap / len(llm_assets)
            if score > best_score:
                best_score = score
                best_path = subtree_path
                best_assets = assets

        if llm_syntax_broken and best_path is None:
            stem = Path(path).stem
            for candidate in (stem, f"{stem}_2", stem.removesuffix("_2")):
                candidate_path = f"lib/widgets/{candidate}.dart"
                if candidate_path in subtree_result.files:
                    best_path = candidate_path
                    best_assets = subtree_assets.get(candidate_path, frozenset())
                    best_score = 1.0
                    break

        if best_path is None or (best_score < 0.5 and not llm_syntax_broken):
            continue

        spec = spec_by_path.get(best_path)
        if (
            not llm_syntax_broken
            and spec is not None
            and len(llm_assets) >= spec.vector_count
        ):
            continue
        if (
            not llm_syntax_broken
            and spec is None
            and len(llm_assets) >= len(best_assets) * 0.6
        ):
            continue

        llm_class = _extract_widget_class_name(llm_content)
        subtree_class = _extract_widget_class_name(subtree_result.files[best_path])
        if llm_class is None or subtree_class is None:
            continue

        spec = spec_by_path.get(best_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(updated, exclude_paths=frozenset({path})),
        )
        merged = _rename_widget_class(subtree_result.files[best_path], subtree_class, target_class)
        updated[path] = merged

    for subtree_path, subtree_content in subtree_result.files.items():
        if subtree_path not in updated:
            continue
        current = updated[subtree_path]
        if current == subtree_content:
            continue
        llm_class = _extract_widget_class_name(current)
        subtree_class = _extract_widget_class_name(subtree_content)
        if llm_class is None or subtree_class is None:
            updated[subtree_path] = subtree_content
            continue
        spec = spec_by_path.get(subtree_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(
                updated,
                exclude_paths=frozenset({subtree_path}),
            ),
        )
        updated[subtree_path] = _rename_widget_class(subtree_content, subtree_class, target_class)

    return updated


def _primary_widget_class_region(screen_code: str) -> tuple[int, int]:
    """Return the byte range of the main screen widget class in ``screenCode``."""
    matches = list(_WIDGET_CLASS_DECL_RE.finditer(screen_code))
    if not matches:
        return 0, len(screen_code)
    chosen = matches[-1]
    for match in matches:
        name_match = re.search(
            r"class\s+(\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)",
            screen_code[match.start() : match.start() + 120],
        )
        if name_match is not None and name_match.group(1).endswith("Screen"):
            chosen = match
            break
    chosen_index = matches.index(chosen)
    region_start = chosen.start()
    region_end = (
        matches[chosen_index + 1].start()
        if chosen_index + 1 < len(matches)
        else len(screen_code)
    )
    return region_start, region_end


def _iter_positioned_blocks(
    screen_code: str,
    *,
    region_start: int = 0,
    region_end: int | None = None,
) -> Iterator[tuple[int, int, str]]:
    """Yield ``(start, paren_end, block)`` for standalone ``Positioned(`` calls."""
    end_bound = len(screen_code) if region_end is None else region_end
    index = region_start
    while index < end_bound:
        match = _POSITIONED_CALL_RE.search(screen_code, index, end_bound)
        if match is None:
            break
        start = match.start()
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None or paren_end >= end_bound:
            index = match.end()
            continue
        yield start, paren_end, screen_code[start : paren_end + 1]
        index = paren_end + 1


def _find_matching_paren(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "(":
        return None
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue
        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _resolve_widget_class_name(
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult,
    spec: SubtreeWidgetSpec,
) -> str:
    widget_path = f"lib/widgets/{spec.file_name}.dart"
    widget_source = planned_files.get(widget_path, subtree_result.files.get(widget_path, ""))
    return _extract_widget_class_name(widget_source) or spec.class_name


def _value_near(value: str, expected: float, *, tolerance: float = 1.5) -> bool:
    try:
        return abs(float(value) - expected) <= tolerance
    except ValueError:
        return False


def _format_placement_token(value: float) -> str:
    return f"{value:g}" if value != int(value) else str(int(value))


def _block_uses_widget_child(block: str, class_name: str) -> bool:
    return bool(
        re.search(
            rf"child:\s*(?:const\s+)?{re.escape(class_name)}\s*\(\s*\)",
            block,
            re.DOTALL,
        )
    )


def _block_matches_placement(
    block: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    tolerance: float = 4.0,
) -> bool:
    from figma_flutter_agent.generator.dart_postprocess import unscale_design_expressions

    normalized = unscale_design_expressions(block)
    left_match = re.search(r"left:\s*([\d.]+)", normalized)
    top_match = re.search(r"top:\s*([\d.]+)", normalized)
    width_match = re.search(r"width:\s*([\d.]+)", normalized)
    height_match = re.search(r"height:\s*([\d.]+)", normalized)
    if left_match is None or top_match is None:
        return False
    if not (
        _value_near(left_match.group(1), left, tolerance=tolerance)
        and _value_near(top_match.group(1), top, tolerance=tolerance)
    ):
        return False
    if width_match is not None and height_match is not None:
        return _value_near(width_match.group(1), width, tolerance=tolerance) and _value_near(
            height_match.group(1), height, tolerance=tolerance
        )
    right_match = re.search(r"right:\s*([\d.]+)", normalized)
    height_only_match = re.search(r"height:\s*([\d.]+)", normalized)
    return (
        right_match is not None
        and height_only_match is not None
        and _value_near(left_match.group(1), left, tolerance=tolerance)
        and _value_near(right_match.group(1), left, tolerance=tolerance)
        and _value_near(height_only_match.group(1), height, tolerance=tolerance)
    )


def _build_positioned_widget_replacement(
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    left_token = _format_placement_token(left)
    top_token = _format_placement_token(top)
    width_token = _format_placement_token(width)
    height_token = _format_placement_token(height)
    return (
        "Positioned(\n"
        f"                        left: {left_token},\n"
        f"                        top: {top_token},\n"
        f"                        width: {width_token},\n"
        f"                        height: {height_token},\n"
        f"                        child: const {class_name}(),\n"
        "                      )"
    )


def _replace_positioned_at_placement(
    screen_code: str,
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    """Replace the first Positioned block at Figma stackPlacement with a prebuilt widget."""
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if _block_uses_widget_child(block, class_name):
            continue
        if not _block_matches_placement(
            block,
            left=left,
            top=top,
            width=width,
            height=height,
        ):
            continue
        replacement = _build_positioned_widget_replacement(
            class_name=class_name,
            left=left,
            top=top,
            width=width,
            height=height,
        )
        candidate = screen_code[:start] + replacement + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def _accept_replacement_if_valid(
    original: str,
    candidate: str,
    *,
    class_name: str,
) -> str:
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(candidate)
    if delimiter_error is None:
        return candidate
    logger.warning(
        "Skipped subtree Positioned replacement for {}: {}",
        class_name,
        delimiter_error,
    )
    return original


def _replace_empty_subtree_placeholder(
    screen_code: str,
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    """Replace an empty ``SizedBox`` placeholder with a prebuilt subtree widget."""
    if re.search(rf"\b{re.escape(class_name)}\s*\(", screen_code):
        return screen_code

    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not re.search(r"child:\s*(?:const\s+)?SizedBox\s*\(\s*\)", block):
            continue
        left_match = re.search(r"left:\s*([\d.]+)", block)
        top_match = re.search(r"top:\s*([\d.]+)", block)
        width_match = re.search(r"width:\s*([\d.]+)", block)
        height_match = re.search(r"height:\s*([\d.]+)", block)
        if (
            left_match is None
            or top_match is None
            or width_match is None
            or height_match is None
            or not _value_near(left_match.group(1), left)
            or not _value_near(top_match.group(1), top)
            or not _value_near(width_match.group(1), width)
            or not _value_near(height_match.group(1), height)
        ):
            continue
        child_re = r"child:\s*(?:const\s+)?SizedBox\s*\(\s*\)"
        new_block = re.sub(child_re, f"child: const {class_name}()", block, count=1)
        candidate = screen_code[:start] + new_block + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


def _find_best_tree_node_for_assets(
    root: CleanDesignTreeNode,
    widget_assets: frozenset[str],
) -> CleanDesignTreeNode | None:
    """Return the clean-tree subtree that best matches a planned widget asset set."""
    if not widget_assets:
        return None
    ranked: list[tuple[float, CleanDesignTreeNode]] = []
    for node in _collect_all_nodes(root):
        node_assets = _collect_node_asset_keys(node)
        if not node_assets:
            continue
        overlap = len(node_assets & widget_assets)
        if overlap == 0:
            continue
        score = overlap / len(widget_assets)
        if score < 0.4:
            continue
        ranked.append((score, node))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _, node in ranked:
        if node.stack_placement is not None:
            return node
    return ranked[0][1]


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _planned_widget_specs(
    planned_files: dict[str, str],
) -> list[tuple[str, frozenset[str], int]]:
    specs: list[tuple[str, frozenset[str], int]] = []
    for path, content in planned_files.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        assets = _extract_asset_paths(content)
        if class_name is None or not assets:
            continue
        specs.append((class_name, assets, len(assets)))
    specs.sort(key=lambda item: item[2], reverse=True)
    return specs


def _should_replace_block_with_widget(
    block: str,
    *,
    class_name: str,
    widget_assets: frozenset[str],
) -> bool:
    block_assets = _extract_asset_paths(block)
    overlap = block_assets & widget_assets
    if len(overlap) < max(1, math.ceil(len(widget_assets) * 0.4)):
        return False
    sole_widget = re.search(
        rf"child:\s*(?:const\s+)?{re.escape(class_name)}\s*\(\s*\)\s*(?:,|\))",
        block,
        re.DOTALL,
    )
    if sole_widget is not None and not block_assets:
        return False
    return bool(block_assets)


def _replace_positioned_inlining_with_widget(
    screen_code: str,
    *,
    class_name: str,
    widget_assets: frozenset[str],
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    """Replace a Positioned block that inlines widget assets with ``const WidgetClass()``."""
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not _should_replace_block_with_widget(
            block,
            class_name=class_name,
            widget_assets=widget_assets,
        ):
            continue
        left_match = re.search(r"left:\s*([\d.]+)", block)
        if left_match is not None and not _value_near(left_match.group(1), left, tolerance=4.0):
            continue
        top_match = re.search(r"top:\s*([\d.]+)", block)
        if top_match is not None and not _value_near(top_match.group(1), top, tolerance=4.0):
            continue
        replacement = _build_positioned_widget_replacement(
            class_name=class_name,
            left=left,
            top=top,
            width=width,
            height=height,
        )
        candidate = screen_code[:start] + replacement + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def force_subtree_widgets_at_placement(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult,
    planned_files: dict[str, str],
) -> str:
    """Pin prebuilt subtree widgets at their Figma stackPlacement regardless of LLM inlining."""
    updated = screen_code
    for spec in subtree_result.specs:
        placement = spec.representative.stack_placement
        if placement is None or placement.width is None or placement.height is None:
            continue
        class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
        updated = _replace_positioned_at_placement(
            updated,
            class_name=class_name,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
        )
    return updated


def replace_inlined_planned_widgets(
    screen_code: str,
    *,
    planned_files: dict[str, str],
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Swap LLM-inlined SVG stacks for prebuilt widget classes when assets overlap."""
    updated = screen_code
    for class_name, widget_assets, _ in _planned_widget_specs(planned_files):
        node = _find_best_tree_node_for_assets(clean_tree, widget_assets)
        if node is None or node.stack_placement is None:
            continue
        placement = node.stack_placement
        if placement.width is None or placement.height is None:
            continue
        before = updated
        updated = _replace_positioned_at_placement(
            updated,
            class_name=class_name,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
        )
        if updated != before:
            continue
        updated = _replace_positioned_inlining_with_widget(
            updated,
            class_name=class_name,
            widget_assets=widget_assets,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
        )
    return updated


def _social_button_label_in_subtree(node: CleanDesignTreeNode) -> str | None:
    """Return a social login label when any descendant TEXT matches."""
    for current in _collect_all_nodes(node):
        if current.type != NodeType.TEXT or not current.text:
            continue
        upper = current.text.upper()
        for social_label in _SOCIAL_BUTTON_LABELS:
            if social_label in upper:
                return social_label
    return None


def _labeled_social_button_stack(node: CleanDesignTreeNode) -> str | None:
    """Return the button label when *node* is a Figma stack for a social login row."""
    if node.type != NodeType.STACK:
        return None
    return _social_button_label_in_subtree(node)


def _filter_outermost_social_button_stacks(
    candidates: list[tuple[str, CleanDesignTreeNode]],
) -> list[tuple[str, CleanDesignTreeNode]]:
    """Keep only the largest stack per label (drop inner groups that also match)."""
    if len(candidates) <= 1:
        return candidates

    def _descendant_of(ancestor: CleanDesignTreeNode, node: CleanDesignTreeNode) -> bool:
        if ancestor.id == node.id:
            return False
        return node.id in {item.id for item in _collect_all_nodes(ancestor)}

    outermost: list[tuple[str, CleanDesignTreeNode]] = []
    for label, node in candidates:
        if any(_descendant_of(other, node) for _, other in candidates if other.id != node.id):
            continue
        outermost.append((label, node))
    return outermost


def _collect_labeled_social_button_stacks(
    root: CleanDesignTreeNode,
) -> list[tuple[str, CleanDesignTreeNode]]:
    candidates: list[tuple[str, CleanDesignTreeNode]] = []
    for node in _collect_all_nodes(root):
        if node.type != NodeType.STACK:
            continue
        label = _social_button_label_in_subtree(node)
        if label is None:
            continue
        placement = node.stack_placement
        row_width = placement.width if placement is not None else node.sizing.width
        row_height = placement.height if placement is not None else node.sizing.height
        if row_width is None or row_height is None:
            continue
        if row_width < 200.0 or row_height < 40.0:
            continue
        candidates.append((label, node))
    return _filter_outermost_social_button_stacks(candidates)


def _build_positioned_body_replacement(
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    body: str,
) -> str:
    left_token = _format_placement_token(left)
    top_token = _format_placement_token(top)
    width_token = _format_placement_token(width)
    height_token = _format_placement_token(height)
    return (
        "Positioned(\n"
        f"              left: {left_token},\n"
        f"              top: {top_token},\n"
        f"              width: {width_token},\n"
        f"              height: {height_token},\n"
        f"              child: {body.strip()},\n"
        "            )"
    )


def _replace_material_social_button(
    screen_code: str,
    label: str,
    replacement: str,
) -> str:
    """Replace a Material social button with a deterministic InkWell stack from Figma."""
    text_match = re.search(
        rf"Text\s*\(\s*['\"]({re.escape(label)})['\"]",
        screen_code,
        re.IGNORECASE,
    )
    if text_match is None:
        return screen_code
    text_index = text_match.start()
    button_start = -1
    for pattern in (
        r"FilledButton\s*\(",
        r"OutlinedButton\s*\(",
        r"ElevatedButton\s*\(",
        r"Material\s*\(",
        r"Container\s*\(",
    ):
        for match in re.finditer(pattern, screen_code[:text_index]):
            if match.start() > button_start:
                button_start = match.start()
    if button_start < 0:
        return screen_code
    paren_open = screen_code.find("(", button_start)
    if paren_open < 0:
        return screen_code
    paren_close = _find_matching_paren(screen_code, paren_open)
    if paren_close is None:
        return screen_code
    candidate = (
        screen_code[:button_start] + replacement.strip() + screen_code[paren_close + 1 :]
    )
    return _accept_replacement_if_valid(
        screen_code,
        candidate,
        class_name=f"social:{label}",
    )


def _replace_positioned_social_row_by_label(
    screen_code: str,
    label: str,
    replacement: str,
    stack_node: CleanDesignTreeNode,
) -> str:
    """Replace the innermost ``Positioned`` social row that contains ``label`` text."""
    text_matches = list(
        re.finditer(
            rf"Text\s*\(\s*['\"]({re.escape(label)})['\"]",
            screen_code,
            re.IGNORECASE,
        )
    )
    if not text_matches:
        return screen_code
    placement = stack_node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return screen_code
    positioned_body = _build_positioned_body_replacement(
        left=placement.left,
        top=placement.top,
        width=placement.width,
        height=placement.height,
        body=replacement,
    )
    region_start, region_end = _primary_widget_class_region(screen_code)
    for text_match in text_matches:
        text_index = text_match.start()
        best_start = -1
        best_end = -1
        for start, paren_end, block in _iter_positioned_blocks(
            screen_code,
            region_start=region_start,
            region_end=region_end,
        ):
            if (
                start <= text_index <= paren_end
                and label.upper() in block.upper()
                and start > best_start
            ):
                best_start = start
                best_end = paren_end
        if best_start < 0:
            continue
        candidate = screen_code[:best_start] + positioned_body + screen_code[best_end + 1 :]
        accepted = _accept_replacement_if_valid(
            screen_code,
            candidate,
            class_name=f"social:{label}",
        )
        if accepted != screen_code:
            return accepted
    return screen_code


def _replace_social_button_at_placement(
    screen_code: str,
    *,
    stack_node: CleanDesignTreeNode,
    replacement: str,
    label: str,
) -> str:
    """Replace a Positioned social row (Material button or subtree widget) at Figma placement."""
    placement = stack_node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return screen_code
    left = placement.left
    top = placement.top
    width = placement.width
    height = placement.height
    positioned_body = _build_positioned_body_replacement(
        left=left,
        top=top,
        width=width,
        height=height,
        body=replacement,
    )
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not _block_matches_placement(
            block,
            left=left,
            top=top,
            width=width,
            height=height,
            tolerance=6.0,
        ):
            continue
        label_in_block = label.upper() in block.upper()
        widget_only = bool(
            re.search(r"child:\s*(?:const\s+)?\w+Widget\s*\(\s*\)", block)
            and not label_in_block
        )
        if not label_in_block and not widget_only:
            continue
        candidate = screen_code[:start] + positioned_body + screen_code[paren_end + 1 :]
        accepted = _accept_replacement_if_valid(
            screen_code,
            candidate,
            class_name=f"social:{label}",
        )
        if accepted != screen_code:
            return accepted
    return screen_code


def _remove_duplicate_subtree_widget_placements(
    screen_code: str,
    *,
    widget_class_names: frozenset[str],
    keep_placements: list[tuple[float, float, float, float]],
) -> str:
    """Drop extra ``const FooWidget()`` layers after the social row was rebuilt."""
    if not widget_class_names:
        return screen_code
    removals: list[tuple[int, int]] = []
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not any(_block_uses_widget_child(block, name) for name in widget_class_names):
            continue
        left_match = re.search(r"left:\s*([\d.]+)", block)
        top_match = re.search(r"top:\s*([\d.]+)", block)
        width_match = re.search(r"width:\s*([\d.]+)", block)
        height_match = re.search(r"height:\s*([\d.]+)", block)
        if (
            left_match is None
            or top_match is None
            or width_match is None
            or height_match is None
        ):
            continue
        if any(
            _block_matches_placement(
                block,
                left=keep_left,
                top=keep_top,
                width=keep_width,
                height=keep_height,
                tolerance=6.0,
            )
            for keep_left, keep_top, keep_width, keep_height in keep_placements
        ):
            continue
        removals.append((start, paren_end + 1))
    updated = screen_code
    for start, end in sorted(removals, reverse=True):
        leading = updated[:start].rstrip()
        trailing = updated[end:].lstrip()
        if trailing.startswith(","):
            trailing = trailing[1:].lstrip()
        elif leading.endswith(","):
            leading = leading[:-1].rstrip()
        updated = f"{leading}\n{trailing}" if leading and trailing else leading + trailing
    return updated


def fix_llm_social_button_inner_stacks(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    subtree_widget_classes: frozenset[str] = frozenset(),
) -> str:
    """Rebuild social login rows from deterministic layout (fill, icon, label positions)."""
    updated = screen_code
    keep_placements: list[tuple[float, float, float, float]] = []
    for _label, stack_node in _collect_labeled_social_button_stacks(clean_tree):
        label = _social_button_label_in_subtree(stack_node)
        if label is None:
            continue
        body = render_node_body(
            stack_node,
            uses_svg=uses_svg,
            parent_type=None,
        )
        updated = _replace_positioned_social_row_by_label(
            updated,
            label,
            body,
            stack_node,
        )
        updated = _replace_material_social_button(updated, label, body)
        updated = _replace_social_button_at_placement(
            updated,
            stack_node=stack_node,
            replacement=body,
            label=label,
        )
        placement = stack_node.stack_placement
        if placement is not None and placement.width is not None and placement.height is not None:
            keep_placements.append(
                (placement.left, placement.top, placement.width, placement.height)
            )
    if subtree_widget_classes and keep_placements:
        updated = _remove_duplicate_subtree_widget_placements(
            updated,
            widget_class_names=subtree_widget_classes,
            keep_placements=keep_placements,
        )
    return updated


def reconcile_llm_screen_with_subtrees(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult | None,
    planned_files: dict[str, str],
    clean_tree: CleanDesignTreeNode,
    uses_svg: bool = True,
) -> str:
    """Patch LLM screen bodies to use prebuilt subtree widgets and Figma-accurate copy."""
    from figma_flutter_agent.generator.llm_dart import apply_clean_tree_text_to_screen

    updated = screen_code
    if subtree_result is not None:
        updated = force_subtree_widgets_at_placement(
            updated,
            subtree_result=subtree_result,
            planned_files=planned_files,
        )
        for spec in subtree_result.specs:
            placement = spec.representative.stack_placement
            if placement is None or placement.width is None or placement.height is None:
                continue
            class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
            updated = _replace_empty_subtree_placeholder(
                updated,
                class_name=class_name,
                left=placement.left,
                top=placement.top,
                width=placement.width,
                height=placement.height,
            )
    updated = replace_inlined_planned_widgets(
        updated,
        planned_files=planned_files,
        clean_tree=clean_tree,
    )
    updated = apply_clean_tree_text_to_screen(updated, clean_tree)
    subtree_classes = frozenset()
    if subtree_result is not None:
        subtree_classes = frozenset(
            _resolve_widget_class_name(planned_files, subtree_result, spec)
            for spec in subtree_result.specs
        )
    from figma_flutter_agent.generator.ambient_background import (
        ensure_centered_design_canvas,
        fix_ambient_background_responsiveness,
    )
    from figma_flutter_agent.generator.dart_postprocess import (
        strip_llm_responsive_layout_builder,
        strip_llm_viewport_scale_hack,
    )

    updated = strip_llm_viewport_scale_hack(updated)
    updated = strip_llm_responsive_layout_builder(updated)
    updated = fix_llm_social_button_inner_stacks(
        updated,
        clean_tree,
        uses_svg=uses_svg,
        subtree_widget_classes=subtree_classes,
    )
    updated = fix_ambient_background_responsiveness(
        updated,
        clean_tree,
        uses_svg=uses_svg,
    )
    updated = ensure_centered_design_canvas(updated)
    from figma_flutter_agent.generator.planned_dart import strip_llm_relative_widget_imports

    updated = strip_llm_relative_widget_imports(updated)
    return _finalize_reconciled_screen(screen_code, updated)


def _finalize_reconciled_screen(original: str, reconciled: str) -> str:
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(reconciled)
    if delimiter_error is None:
        return reconciled
    logger.warning(
        "Subtree reconcile produced invalid Dart syntax ({}); keeping original screenCode",
        delimiter_error,
    )
    return original
