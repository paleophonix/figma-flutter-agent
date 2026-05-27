"""Deterministic ambient background layer for classic absolute LLM screens."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.layout_renderer import render_node_body
from figma_flutter_agent.generator.llm_dart import _find_matching_paren, validate_dart_delimiters
from figma_flutter_agent.parser.interaction import _ACTION_HINTS, _INPUT_HINTS
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_INTERACTIVE_TEXT_HINTS = tuple(
    dict.fromkeys(
        (
            *_ACTION_HINTS,
            *_INPUT_HINTS,
            "or log in",
            "welcome",
            "forgot password",
        )
    )
)
_SVG_ASSET_RE = re.compile(r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_IMAGE_ASSET_RE = re.compile(r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_POSITIONED_FILL_RE = re.compile(r"Positioned\.fill\s*\(")
_CANVAS_SIZE_RE = re.compile(
    r"const\s+double\s+(?:canvasWidth|designWidth)\s*=\s*(?P<width>[\d.]+)\s*;\s*"
    r"const\s+double\s+(?:canvasHeight|designHeight)\s*=\s*(?P<height>[\d.]+)\s*;",
    re.DOTALL,
)


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _subtree_has_interactive_ui(node: CleanDesignTreeNode) -> bool:
    for current in _collect_all_nodes(node):
        if current.type in {
            NodeType.BUTTON,
            NodeType.INPUT,
            NodeType.CHECKBOX,
            NodeType.SWITCH,
            NodeType.RADIO,
            NodeType.RADIO_GROUP,
            NodeType.DROPDOWN,
            NodeType.SLIDER,
            NodeType.TABS,
            NodeType.BOTTOM_NAV,
        }:
            return True
        if current.type == NodeType.TEXT and current.text:
            lower = current.text.strip().lower()
            if any(hint in lower for hint in _INTERACTIVE_TEXT_HINTS):
                return True
    return False


def collect_ambient_background_children(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return decorative root children that should sit behind the interactive canvas."""
    if root.type != NodeType.STACK:
        return []
    ambient: list[CleanDesignTreeNode] = []
    for child in root.children:
        if not _is_ambient_background_child(child):
            continue
        ambient.append(child)
    return ambient


def _is_ambient_background_child(node: CleanDesignTreeNode) -> bool:
    if _subtree_has_interactive_ui(node):
        return False
    if node.stack_placement is None:
        return False
    if node.type == NodeType.VECTOR and node.vector_asset_key:
        return True
    if node.type == NodeType.IMAGE and node.image_asset_key:
        return True
    if node.type == NodeType.STACK:
        return any(
            descendant.type in {NodeType.VECTOR, NodeType.IMAGE}
            and (descendant.vector_asset_key or descendant.image_asset_key)
            for descendant in _collect_all_nodes(node)
        )
    return False


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


def render_ambient_background_layer(
    root: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Render the cover-scaled ambient background ``Positioned.fill`` layer."""
    children = collect_ambient_background_children(root)
    width = root.sizing.width
    height = root.sizing.height
    if not children or width is None or height is None or width <= 0 or height <= 0:
        return None
    bodies = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=root,
        )
        for child in children
    ]
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    return (
        "Positioned.fill(\n"
        "                    child: Center(\n"
        "                      child: SizedBox(\n"
        f"                        width: {width_token},\n"
        f"                        height: {height_token},\n"
        "                        child: Stack(\n"
        "                          clipBehavior: Clip.none,\n"
        f"                          children: [{', '.join(bodies)}],\n"
        "                        ),\n"
        "                      ),\n"
        "                    ),\n"
        "                  )"
    )


def _extract_asset_paths(block: str) -> frozenset[str]:
    paths: set[str] = set()
    for pattern in (_SVG_ASSET_RE, _IMAGE_ASSET_RE):
        paths.update(match.group("path") for match in pattern.finditer(block))
    return frozenset(paths)


def _iter_positioned_blocks(source: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    for match in re.finditer(r"(?<![A-Za-z0-9_])Positioned(?:\.fill)?\s*\(", source):
        start = match.start()
        paren_open = match.end() - 1
        paren_close = _find_matching_paren(source, paren_open)
        if paren_close is None:
            continue
        blocks.append((start, paren_close + 1, source[start : paren_close + 1]))
    return blocks


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


def _hoist_ambient_background_behind_canvas(
    screen_code: str,
    *,
    ambient_layer: str,
) -> str | None:
    """Place the ambient layer behind the centered design canvas (not inside it)."""
    if "StackFit.expand" in screen_code and ambient_layer.strip() in screen_code:
        return screen_code
    safe_match = re.search(r"SafeArea\s*\(", screen_code)
    if safe_match is None:
        return None
    safe_open = safe_match.end() - 1
    safe_close = _find_matching_paren(screen_code, safe_open)
    if safe_close is None:
        return None
    child_match = re.search(r"child:\s*", screen_code[safe_match.start() : safe_close + 1])
    if child_match is None:
        return None
    child_start = safe_match.start() + child_match.end()
    foreground = screen_code[child_start:safe_close].strip().rstrip(",")
    if foreground.startswith("Stack(") and "StackFit.expand" in foreground:
        return screen_code
    hoisted = (
        screen_code[:child_start]
        + "Stack(\n"
        "          fit: StackFit.expand,\n"
        "          children: [\n"
        f"            {ambient_layer},\n"
        f"            {foreground},\n"
        "          ],\n"
        "        )"
        + screen_code[safe_close:]
    )
    return hoisted


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

    delimiter_error = validate_dart_delimiters(updated)
    if delimiter_error is not None:
        logger.warning(
            "Ambient background reconcile produced invalid Dart ({}); keeping prior screenCode",
            delimiter_error,
        )
        return screen_code
    return updated


_CENTERED_FOREGROUND_LAYER_RE = re.compile(
    r"^Positioned\.fill\s*\(\s*child:\s*Center\s*\(\s*child:\s*(?:GestureDetector|SizedBox)\s*\(",
    re.DOTALL,
)


def _find_matching_bracket(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "[":
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
        if char == "[":
            depth += 1
            continue
        if char == "]":
            depth -= 1
            if depth == 0:
                return index
    return None


def _is_ambient_cover_block(block: str) -> bool:
    """True for legacy cover layers or the centered ambient hoist layer."""
    if "Positioned.fill" not in block:
        return False
    if "BoxFit.cover" in block:
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


def _iter_direct_stack_children_blocks(
    source: str,
    list_open: int,
    list_close: int,
) -> list[tuple[int, int, str]]:
    """Yield widget blocks at depth 0 inside a ``children: [ ... ]`` list."""
    blocks: list[tuple[int, int, str]] = []
    index = list_open + 1
    while index < list_close:
        while index < list_close and source[index] in " \t\n\r,":
            index += 1
        if index >= list_close:
            break
        block_start = index
        depth_paren = 0
        depth_bracket = 0
        in_string = False
        string_quote = ""
        escape = False
        while index < list_close:
            char = source[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == string_quote:
                    in_string = False
                index += 1
                continue
            if char in {"'", '"'}:
                in_string = True
                string_quote = char
                index += 1
                continue
            if char == "(":
                depth_paren += 1
            elif char == ")":
                depth_paren -= 1
            elif char == "[":
                depth_bracket += 1
            elif char == "]":
                depth_bracket -= 1
            elif char == "," and depth_paren == 0 and depth_bracket == 0:
                break
            index += 1
        block_end = index
        block = source[block_start:block_end].strip()
        if block:
            blocks.append((block_start, block_end, block))
    return blocks


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

    merged_stack_children: list[str] = []
    foreground_parts: list[str] = []
    for _start, _end, block in _iter_direct_stack_children_blocks(screen_code, list_open, list_close):
        stripped = block.strip().rstrip(",")
        if _CENTERED_FOREGROUND_LAYER_RE.match(stripped):
            return screen_code
        if _is_responsive_layout_builder_foreground(stripped):
            from figma_flutter_agent.generator.dart_postprocess import (
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
