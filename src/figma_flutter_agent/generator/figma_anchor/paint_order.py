"""Screen Stack paint-order normalization."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_bracket as _find_matching_bracket,
)
from figma_flutter_agent.generator.figma_anchor.blocks import (
    _design_stack_children_bounds,
    _finalize_spliced_dart_fragment,
)

_BACKGROUND_WIDGET_RE = re.compile(r"(?:const\s+)?\w*Background\w*\s*\(")


def _split_top_level_list_items(segment: str) -> list[str]:
    """Split a Dart list body on commas that are not inside nested brackets."""
    items: list[str] = []
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    start = 0
    for index, char in enumerate(segment):
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
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            piece = segment[start:index].strip()
            if piece:
                items.append(segment[start:index])
            start = index + 1
    tail = segment[start:].strip()
    if tail:
        items.append(segment[start:])
    return items


def _is_background_stack_child(item: str) -> bool:
    stripped = item.strip()
    if _BACKGROUND_WIDGET_RE.search(stripped):
        return True
    return "Positioned.fill" in stripped and (
        "BoxFit.cover" in stripped or "BoxFit.fill" in stripped
    )


def _is_positioned_overlay_child(item: str) -> bool:
    stripped = item.strip()
    return stripped.startswith("Positioned(") or stripped.startswith("const Positioned(")


def _main_screen_stack_children_bounds(screen_code: str) -> tuple[int, int] | None:
    bounds = _design_stack_children_bounds(screen_code)
    if bounds is not None:
        return bounds
    for pattern in (
        r"Stack\s*\(\s*fit:\s*StackFit\.expand,\s*children:\s*\[",
        r"Stack\s*\(\s*[^)]*children:\s*\[",
    ):
        match = re.search(pattern, screen_code, re.DOTALL)
        if match is None:
            continue
        list_open = match.end() - 1
        list_close = _find_matching_bracket(screen_code, list_open, "[", "]")
        if list_close is not None:
            return list_open + 1, list_close
    return None


def ensure_screen_stack_paint_order(screen_code: str) -> str:
    """Paint backgrounds first, content next, ``Positioned`` overlays last in the screen ``Stack``."""
    bounds = _main_screen_stack_children_bounds(screen_code)
    if bounds is None:
        return screen_code
    start, end = bounds
    segment = screen_code[start:end]
    items = _split_top_level_list_items(segment)
    if len(items) < 2:
        return screen_code
    backgrounds: list[str] = []
    content: list[str] = []
    overlays: list[str] = []
    for item in items:
        if not item.strip():
            continue
        if _is_background_stack_child(item):
            backgrounds.append(item)
        elif _is_positioned_overlay_child(item):
            overlays.append(item)
        else:
            content.append(item)
    ordered = backgrounds + content + overlays
    if ordered == items:
        return screen_code
    rebuilt = ",\n".join(piece.strip() for piece in ordered if piece.strip())
    if segment.startswith("\n"):
        rebuilt = f"\n{rebuilt}"
    if segment.endswith("\n"):
        rebuilt = f"{rebuilt}\n            "
    candidate = screen_code[:start] + rebuilt.strip() + screen_code[end:]
    return _finalize_spliced_dart_fragment(
        screen_code,
        candidate,
        label="screen stack paint order",
    )
