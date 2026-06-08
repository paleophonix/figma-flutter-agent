"""Layout-level contracts for generated Dart sources."""

from __future__ import annotations

import re

from figma_flutter_agent.errors import GenerationError

LAYOUT_SCROLLABLE_RE = re.compile(
    r"\b(ListView|GridView|PageView|SingleChildScrollView|CustomScrollView)\b"
)

_LAYOUT_FIXED_DIM_RE = re.compile(r"\b(width|height):\s*(\d+(?:\.\d+)?)")
_LAYOUT_VIEWPORT_SCALE_RE = re.compile(
    r"FittedBox\s*\(\s*fit:\s*BoxFit\.(?:scaleDown|contain)"
)
_NARROW_VIEWPORT_MAX_PX = 320


def layout_scales_to_narrow_viewport(content: str) -> bool:
    """True when the layout file shrinks or scrolls a fixed artboard for narrow widths."""
    if LAYOUT_SCROLLABLE_RE.search(content):
        return True
    return _LAYOUT_VIEWPORT_SCALE_RE.search(content) is not None


def positioned_constraint_arg_strings(layout_source: str) -> list[str]:
    """Extract argument strings for each ``Positioned(…, child:`` in layout Dart."""
    args_list: list[str] = []
    needle = "Positioned("
    search_from = 0
    while True:
        start = layout_source.find(needle, search_from)
        if start < 0:
            break
        depth = 1
        j = start + len(needle)
        while j < len(layout_source):
            char = layout_source[j]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    args_list.append(layout_source[start + len(needle) : j])
                    search_from = j + 1
                    break
            j += 1
        else:
            break
    return args_list


def assert_valid_positioned_fields(layout_source: str, *, layout_path: str) -> None:
    """Fail when generated ``Positioned`` uses more than two horizontal or vertical pins."""
    for index, args in enumerate(positioned_constraint_arg_strings(layout_source)):
        constraint_args = args.split(", child:", 1)[0]
        horizontal = sum(
            token in constraint_args for token in ("left:", "right:", "width:")
        )
        vertical = sum(
            token in constraint_args for token in ("top:", "bottom:", "height:")
        )
        if horizontal > 2 or vertical > 2:
            raise GenerationError(
                f"Generated layout '{layout_path}' has invalid Positioned #{index + 1}: "
                "Flutter allows at most two of left/right/width and two of top/bottom/height"
            )


def layout_line_skips_narrow_width_check(line: str) -> bool:
    """Return True when a layout line may use bounded pixel widths safely."""
    return any(
        token in line
        for token in (
            "double.infinity",
            "Positioned(",
            "AspectRatio(",
            "PageView(",
            "ListView",
            "GridView",
            "SvgPicture",
        )
    )


def validate_narrow_viewport_layout(planned_files: dict[str, str]) -> None:
    """Codegen contract: layouts must not overflow a 320px logical viewport width."""
    for path, content in planned_files.items():
        if not path.endswith("_layout.dart"):
            continue
        if layout_scales_to_narrow_viewport(content):
            continue
        if "Column(" in content:
            has_stretch = "CrossAxisAlignment.stretch" in content
            has_other_cross = "crossAxisAlignment:" in content and not has_stretch
            if has_other_cross:
                raise GenerationError(
                    f"Generated layout '{path}' must use CrossAxisAlignment.stretch "
                    "for narrow viewports (spec section 7.3)"
                )
        for line in content.splitlines():
            if layout_line_skips_narrow_width_check(line):
                continue
            for dimension, value_str in _LAYOUT_FIXED_DIM_RE.findall(line):
                if dimension != "width":
                    continue
                value = float(value_str)
                if value > _NARROW_VIEWPORT_MAX_PX:
                    raise GenerationError(
                        f"Generated layout '{path}' uses width {value:g}px, which exceeds "
                        f"narrow viewport max ({_NARROW_VIEWPORT_MAX_PX}px); use flexible or scroll layout"
                    )


def count_layout_fixed_pixel_sizes(layout_source: str) -> tuple[int, int]:
    """Count numeric width/height on SizedBox/Container lines in layout files."""
    width_count = 0
    height_count = 0
    for line in layout_source.splitlines():
        if "double.infinity" in line or "SvgPicture.asset" in line:
            continue
        if "Positioned(" in line:
            continue
        if "SizedBox(" not in line and "Container(" not in line:
            continue
        for dimension, _value in _LAYOUT_FIXED_DIM_RE.findall(line):
            if dimension == "width":
                width_count += 1
            else:
                height_count += 1
    return width_count, height_count
