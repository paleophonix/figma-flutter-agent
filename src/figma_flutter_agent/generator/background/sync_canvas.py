"""Center the absolute design canvas inside a ``StackFit.expand`` viewport."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.dart.llm_codegen import (
    _find_matching_paren,
    validate_dart_delimiters,
)

from .sync_blocks import _find_matching_bracket, _iter_direct_stack_children_blocks
from .sync_hoist import _CANVAS_SIZE_RE

_CENTERED_FOREGROUND_LAYER_RE = re.compile(
    r"^Positioned\.fill\s*\(\s*child:\s*Center\s*\(\s*child:\s*(?:GestureDetector|SizedBox)\s*\(",
    re.DOTALL,
)


def _is_ambient_cover_block(block: str) -> bool:
    """True for legacy cover layers or the centered ambient hoist layer."""
    if "Positioned.fill" not in block:
        return False
    if "BoxFit.cover" in block:
        return True
    if "BoxFit.contain" in block and "child: Stack" in block:
        return True
    return "child: Center" in block and "child: Stack" in block


def _is_bare_centered_foreground(block: str) -> bool:
    """True when the LLM wrapped UI in a bare ``Center`` instead of ``Positioned.fill``."""
    return bool(
        re.match(
            r"Center\s*\(\s*child:\s*(?:GestureDetector|SizedBox)\s*\(",
            block.strip(),
            re.DOTALL,
        )
    )


def _design_canvas_stack_children(block: str) -> list[str]:
    """Extract top-level widgets from the design-sized ``Stack`` inside a layer block."""
    stack_match = re.search(r"child:\s*Stack\s*\(", block)
    if stack_match is None:
        return []
    stack_open = stack_match.end() - 1
    stack_close = _find_matching_paren(block, stack_open)
    if stack_close is None:
        return []
    children_key = block.find("children:", stack_open, stack_close)
    if children_key < 0:
        return []
    list_open = block.find("[", children_key)
    if list_open < 0 or list_open > stack_close:
        return []
    list_close = _find_matching_bracket(block, list_open)
    if list_close is None:
        return []
    return [
        child
        for _start, _end, child in _iter_direct_stack_children_blocks(block, list_open, list_close)
    ]


def _is_responsive_layout_builder_foreground(block: str) -> bool:
    """True for LLM ``LayoutBuilder`` layers that scale absolute coordinates."""
    stripped = block.strip()
    if not stripped.startswith("LayoutBuilder("):
        return False
    return "scaleX" in block or "constraints.maxWidth" in block


def ensure_centered_design_canvas(screen_code: str) -> str:
    """Center the absolute design canvas on wide viewports (web/tablet)."""
    size_match = _CANVAS_SIZE_RE.search(screen_code)
    if size_match is None:
        return screen_code
    width = float(size_match.group("width"))
    height = float(size_match.group("height"))
    if width <= 0 or height <= 0:
        return screen_code

    expand_match = re.search(r"Stack\s*\(\s*fit:\s*StackFit\.expand", screen_code)
    if expand_match is not None:
        stack_open = screen_code.find("(", expand_match.start())
    else:
        stack_match = re.search(r"(?:body|child):\s*Stack\s*\(", screen_code)
        if stack_match is None:
            return screen_code
        stack_open = stack_match.end() - 1
    if stack_open < 0:
        return screen_code
    stack_close = _find_matching_paren(screen_code, stack_open)
    if stack_close is None:
        return screen_code
    children_key = screen_code.find("children:", stack_open, stack_close)
    if children_key < 0:
        return screen_code
    list_open = screen_code.find("[", children_key)
    if list_open < 0 or list_open > stack_close:
        return screen_code
    list_close = _find_matching_bracket(screen_code, list_open)
    if list_close is None or list_close > stack_close:
        return screen_code

    if expand_match is not None:
        direct_children = _iter_direct_stack_children_blocks(screen_code, list_open, list_close)
        if any(
            _is_ambient_cover_block(block.strip().rstrip(","))
            for _start, _end, block in direct_children
        ):
            return screen_code

    merged_stack_children: list[str] = []
    foreground_parts: list[str] = []
    for _start, _end, block in _iter_direct_stack_children_blocks(
        screen_code, list_open, list_close
    ):
        stripped = block.strip().rstrip(",")
        if _CENTERED_FOREGROUND_LAYER_RE.match(stripped):
            return screen_code
        if _is_responsive_layout_builder_foreground(stripped):
            from figma_flutter_agent.generator.dart.layout_extract import (
                extract_responsive_layout_builder_stack,
            )

            stack_widget = extract_responsive_layout_builder_stack(stripped)
            if stack_widget is not None:
                merged_stack_children.extend(
                    _design_canvas_stack_children(f"child: {stack_widget}")
                )
                continue
        if _is_ambient_cover_block(stripped) or _is_bare_centered_foreground(stripped):
            merged_stack_children.extend(_design_canvas_stack_children(stripped))
            continue
        foreground_parts.append(stripped)
    if not merged_stack_children and not foreground_parts:
        return screen_code

    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    inner_children = [*merged_stack_children, *foreground_parts]
    if not inner_children:
        return screen_code
    inner_joined = ",\n                    ".join(inner_children)
    centered_layer = (
        "Positioned.fill(\n"
        "            child: Center(\n"
        "              child: SizedBox(\n"
        f"                width: {width_token},\n"
        f"                height: {height_token},\n"
        "                child: Stack(\n"
        "                  clipBehavior: Clip.none,\n"
        "                  children: [\n"
        f"                    {inner_joined},\n"
        "                  ],\n"
        "                ),\n"
        "              ),\n"
        "            ),\n"
        "          )"
    )
    layers = [centered_layer]
    new_children = ",\n            ".join(layers)
    candidate = (
        screen_code[: list_open + 1]
        + f"\n            {new_children},\n          "
        + screen_code[list_close:]
    )
    delimiter_error = validate_dart_delimiters(candidate)
    if delimiter_error is not None:
        logger.warning(
            "Centered design canvas reconcile produced invalid Dart ({}); keeping prior screenCode",
            delimiter_error,
        )
        return screen_code
    return candidate


__all__ = ["ensure_centered_design_canvas"]
