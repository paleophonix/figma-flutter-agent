"""Hoist ambient decorative layers behind the design canvas and sync foreground scaling."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.dart.llm_codegen import (
    _find_matching_paren,
    validate_dart_delimiters,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

from .partition import collect_ambient_background_children
from .render import (
    _collect_node_asset_keys,
    patch_scaffold_background_from_tree,
    render_ambient_background_layer,
)
from .sync_blocks import _extract_asset_paths, _iter_positioned_blocks

_POSITIONED_FILL_RE = re.compile(r"Positioned\.fill\s*\(")
_CANVAS_SIZE_RE = re.compile(
    r"const\s+double\s+(?:canvasWidth|designWidth)\s*=\s*(?P<width>[\d.]+)\s*;\s*"
    r"const\s+double\s+(?:canvasHeight|designHeight)\s*=\s*(?P<height>[\d.]+)\s*;",
    re.DOTALL,
)


def _wrap_positioned_fill_with_cover(block: str, *, width: float, height: float) -> str:
    if "BoxFit.cover" in block:
        return block
    stack_match = re.search(r"child:\s*Stack\s*\(", block)
    if stack_match is None:
        return block
    stack_open = stack_match.end() - 1
    stack_close = _find_matching_paren(block, stack_open)
    if stack_close is None:
        return block
    inner_stack = block[stack_open : stack_close + 1]
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    replacement = (
        "child: FittedBox(\n"
        "                      fit: BoxFit.cover,\n"
        "                      clipBehavior: Clip.hardEdge,\n"
        "                      child: SizedBox(\n"
        f"                        width: {width_token},\n"
        f"                        height: {height_token},\n"
        f"                        child: {inner_stack},\n"
        "                      ),\n"
        "                    )"
    )
    return block[: stack_match.start()] + replacement + block[stack_close + 1 :]


def _remove_ambient_positioned_blocks(screen_code: str, ambient_assets: frozenset[str]) -> str:
    if not ambient_assets:
        return screen_code
    candidates: list[tuple[int, int]] = []
    for start, end, block in _iter_positioned_blocks(screen_code):
        block_assets = _extract_asset_paths(block)
        if not block_assets or not block_assets <= ambient_assets:
            continue
        if "Text(" in block or "Button" in block:
            continue
        candidates.append((start, end))
    if not candidates:
        return screen_code
    # Drop nested matches so removing a parent does not corrupt sibling indices.
    maximal: list[tuple[int, int]] = []
    for start, end in sorted(candidates, key=lambda item: item[1] - item[0], reverse=True):
        if any(parent_start <= start and end <= parent_end for parent_start, parent_end in maximal):
            continue
        maximal.append((start, end))
    updated = screen_code
    for start, end in sorted(maximal, reverse=True):
        leading = updated[:start].rstrip()
        trailing = updated[end:].lstrip()
        if trailing.startswith(","):
            trailing = trailing[1:].lstrip()
        elif leading.endswith(","):
            leading = leading[:-1].rstrip()
        updated = f"{leading}\n{trailing}" if leading and trailing else leading + trailing
    return updated


def _inject_ambient_into_expand_stack(
    screen_code: str,
    *,
    child_start: int,
    ambient_layer: str,
) -> str | None:
    """Prepend ``ambient_layer`` to an existing ``StackFit.expand`` child widget."""
    child_slice = screen_code[child_start:].lstrip()
    if not child_slice.startswith("Stack(") or "StackFit.expand" not in child_slice:
        return None
    if ambient_layer.strip() in screen_code:
        return screen_code
    widget_open = screen_code.find("(", child_start)
    if widget_open < 0:
        return None
    widget_close = _find_matching_paren(screen_code, widget_open)
    if widget_close is None:
        return None
    children_match = re.search(
        r"children:\s*\[",
        screen_code[child_start : widget_close + 1],
    )
    if children_match is None:
        return None
    list_open = child_start + children_match.end() - 1
    return (
        screen_code[: list_open + 1]
        + f"\n            {ambient_layer},"
        + screen_code[list_open + 1 :]
    )


def _hoist_ambient_background_behind_canvas(
    screen_code: str,
    *,
    ambient_layer: str,
) -> str | None:
    """Place the ambient layer behind the centered design canvas (not inside it)."""
    if "StackFit.expand" in screen_code and ambient_layer.strip() in screen_code:
        return screen_code
    safe_match = re.search(r"SafeArea\s*\(", screen_code)
    if safe_match is not None:
        safe_open = safe_match.end() - 1
        safe_close = _find_matching_paren(screen_code, safe_open)
        if safe_close is not None:
            child_match = re.search(r"child:\s*", screen_code[safe_match.start() : safe_close + 1])
            if child_match is not None:
                child_start = safe_match.start() + child_match.end()
                child_widget_open = screen_code.find("(", child_start)
                if child_widget_open < 0:
                    child_widget_open = None
                child_close = (
                    _find_matching_paren(screen_code, child_widget_open)
                    if child_widget_open is not None
                    else None
                )
                if child_close is not None:
                    foreground = screen_code[child_start : child_close + 1].strip().rstrip(",")
                    if foreground.startswith("Stack(") and "StackFit.expand" in foreground:
                        return _inject_ambient_into_expand_stack(
                            screen_code,
                            child_start=child_start,
                            ambient_layer=ambient_layer,
                        )
                    hoisted = (
                        screen_code[:child_start] + "Stack(\n"
                        "          fit: StackFit.expand,\n"
                        "          children: [\n"
                        f"            {ambient_layer},\n"
                        f"            {foreground},\n"
                        "          ],\n"
                        "        )" + screen_code[child_close + 1 :]
                    )
                    return hoisted

    body_match = re.search(r"\bbody:\s*", screen_code)
    if body_match is not None:
        body_start = body_match.end()
        open_paren = screen_code.find("(", body_start)
        if open_paren != -1:
            body_close = _find_matching_paren(screen_code, open_paren)
            if body_close is not None:
                foreground = screen_code[body_start : body_close + 1].strip().rstrip(",")
                if foreground.startswith("Stack(") and "StackFit.expand" in foreground:
                    return _inject_ambient_into_expand_stack(
                        screen_code,
                        child_start=body_start,
                        ambient_layer=ambient_layer,
                    )
                hoisted = (
                    screen_code[:body_start] + "Stack(\n"
                    "          fit: StackFit.expand,\n"
                    "          children: [\n"
                    f"            {ambient_layer},\n"
                    f"            {foreground},\n"
                    "          ],\n"
                    "        )" + screen_code[body_close + 1 :]
                )
                return hoisted

    return None


def fix_ambient_background_responsiveness(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str:
    """Hoist decorative vectors into a cover-scaled background behind the design canvas."""
    ambient_children = collect_ambient_background_children(clean_tree)
    if not ambient_children:
        return screen_code
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return screen_code

    ambient_asset_set: set[str] = set()
    for child in ambient_children:
        ambient_asset_set.update(_collect_node_asset_keys(child))
    ambient_assets = frozenset(ambient_asset_set)
    ambient_layer = render_ambient_background_layer(clean_tree, uses_svg=uses_svg)
    if ambient_layer is None:
        return screen_code

    updated = _remove_ambient_positioned_blocks(screen_code, ambient_assets)
    hoisted = _hoist_ambient_background_behind_canvas(updated, ambient_layer=ambient_layer)
    if hoisted is not None:
        updated = hoisted

    updated = sync_ambient_layer_with_foreground_scaling(updated)
    updated = patch_scaffold_background_from_tree(updated, clean_tree)

    delimiter_error = validate_dart_delimiters(updated)
    if delimiter_error is not None:
        from figma_flutter_agent.generator.dart.llm_codegen import repair_dart_delimiters

        repaired = repair_dart_delimiters(updated)
        if validate_dart_delimiters(repaired) is None:
            logger.warning(
                "Ambient background reconcile produced invalid Dart ({}); "
                "keeping delimiter-repaired screenCode",
                delimiter_error,
            )
            return sync_ambient_layer_with_foreground_scaling(repaired)
        logger.warning(
            "Ambient background reconcile produced invalid Dart ({}); keeping prior screenCode",
            delimiter_error,
        )
        return screen_code
    return updated


def _canvas_size_tokens(screen_code: str) -> tuple[str, str]:
    size_match = _CANVAS_SIZE_RE.search(screen_code)
    if size_match is None:
        return "414", "896"
    width = float(size_match.group("width"))
    height = float(size_match.group("height"))
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    return width_token, height_token


def _ambient_stack_inner(block: str) -> str | None:
    """Return the decorative ``Stack(...)`` subtree from a hoisted ambient layer block."""
    sizedbox_match = re.search(r"SizedBox\s*\(", block)
    if sizedbox_match is None:
        return None
    box_open = sizedbox_match.end() - 1
    box_close = _find_matching_paren(block, box_open)
    if box_close is None:
        return None
    box_inner = block[box_open : box_close + 1]
    stack_match = re.search(r"child:\s*Stack\s*\(", box_inner)
    if stack_match is None:
        return None
    stack_open = box_open + stack_match.end() - 1
    stack_close = _find_matching_paren(block, stack_open)
    if stack_close is None:
        return None
    return block[stack_open : stack_close + 1]


def _rebuild_ambient_positioned_fill(
    *,
    stack_widget: str,
    width_token: str,
    height_token: str,
) -> str:
    return (
        "Positioned.fill(\n"
        "                    child: IgnorePointer(\n"
        "                      child: FittedBox(\n"
        "                        fit: BoxFit.cover,\n"
        "                        clipBehavior: Clip.hardEdge,\n"
        "                        child: SizedBox(\n"
        f"                          width: {width_token},\n"
        f"                          height: {height_token},\n"
        f"                          child: {stack_widget},\n"
        "                        ),\n"
        "                      ),\n"
        "                    ),\n"
        "                  )"
    )


def sync_ambient_layer_with_foreground_scaling(screen_code: str) -> str:
    """Wrap hoisted ambient art in the same ``FittedBox(BoxFit.contain)`` as the UI canvas."""
    if "StackFit.expand" not in screen_code:
        return screen_code
    if not re.search(
        r"Center\s*\(\s*child:\s*FittedBox\s*\(\s*fit:\s*BoxFit\.(?:contain|scaleDown)",
        screen_code,
    ):
        return screen_code

    fill_match = _POSITIONED_FILL_RE.search(screen_code)
    if fill_match is None:
        return screen_code
    fill_open = fill_match.end() - 1
    fill_close = _find_matching_paren(screen_code, fill_open)
    if fill_close is None:
        return screen_code
    block = screen_code[fill_match.start() : fill_close + 1]
    if "FittedBox" in block and (
        "BoxFit.contain" in block or "BoxFit.scaleDown" in block or "BoxFit.cover" in block
    ):
        return screen_code
    stack_widget = _ambient_stack_inner(block)
    if stack_widget is None:
        return screen_code
    width_token, height_token = _canvas_size_tokens(screen_code)
    replacement = _rebuild_ambient_positioned_fill(
        stack_widget=stack_widget,
        width_token=width_token,
        height_token=height_token,
    )
    return screen_code[: fill_match.start()] + replacement + screen_code[fill_close + 1 :]


__all__ = [
    "_ambient_stack_inner",
    "_canvas_size_tokens",
    "_hoist_ambient_background_behind_canvas",
    "_inject_ambient_into_expand_stack",
    "_rebuild_ambient_positioned_fill",
    "_remove_ambient_positioned_blocks",
    "_wrap_positioned_fill_with_cover",
    "fix_ambient_background_responsiveness",
    "sync_ambient_layer_with_foreground_scaling",
    "_CANVAS_SIZE_RE",
]
