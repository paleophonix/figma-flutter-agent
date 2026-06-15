"""Positioned-block parsing, matching, and replacement-string helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator

from loguru import logger

from figma_flutter_agent.generator.subtree.merge import _extract_widget_class_name
from figma_flutter_agent.generator.subtree.spec import SubtreeWidgetResult, SubtreeWidgetSpec

_POSITIONED_CALL_RE = re.compile(r"(?<![A-Za-z0-9_])Positioned\(")
_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+\w+\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)


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
        matches[chosen_index + 1].start() if chosen_index + 1 < len(matches) else len(screen_code)
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


def _planned_widget_class_names(planned_files: dict[str, str]) -> frozenset[str]:
    names: set[str] = set()
    for path, content in planned_files.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        if class_name:
            names.add(class_name)
    return frozenset(names)


def _block_uses_any_planned_widget_child(
    block: str,
    planned_files: dict[str, str],
) -> bool:
    for class_name in _planned_widget_class_names(planned_files):
        if _block_uses_widget_child(block, class_name):
            return True
    return False


def _block_matches_placement(
    block: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    tolerance: float = 4.0,
) -> bool:
    from figma_flutter_agent.generator.dart.postprocess import unscale_design_expressions

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
    figma_id: str | None = None,
) -> str:
    left_token = _format_placement_token(left)
    top_token = _format_placement_token(top)
    width_token = _format_placement_token(width)
    height_token = _format_placement_token(height)
    key_line = f"                        key: ValueKey('figma-{figma_id}'),\n" if figma_id else ""
    return (
        "Positioned(\n"
        f"                        left: {left_token},\n"
        f"                        top: {top_token},\n"
        f"                        width: {width_token},\n"
        f"                        height: {height_token},\n"
        f"{key_line}"
        f"                        child: const {class_name}(),\n"
        "                      )"
    )


def _accept_replacement_if_valid(
    original: str,
    candidate: str,
    *,
    class_name: str,
) -> str:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(candidate)
    if delimiter_error is None:
        return candidate
    logger.warning(
        "Skipped subtree Positioned replacement for {}: {}",
        class_name,
        delimiter_error,
    )
    return original
