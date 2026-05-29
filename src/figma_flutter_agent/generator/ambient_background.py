"""Deterministic ambient background layer for classic absolute LLM screens."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.layout_style import dart_color_expr
from figma_flutter_agent.generator.layout_widget import (
    _apply_stack_position,
    _render_exported_vector,
)
from figma_flutter_agent.generator.llm_dart import _find_matching_paren, validate_dart_delimiters
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

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
    """True when the subtree contains interactive node types (semantic, not copy)."""
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


def _is_navigation_chrome_stack(node: CleanDesignTreeNode) -> bool:
    """Small icon-only stacks (back/close) are controls, not wallpaper."""
    if node.type != NodeType.STACK or node.stack_placement is None:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width > 96 or height > 96 or width < 20 or height < 20:
        return False
    if any(
        descendant.type in {NodeType.BUTTON, NodeType.INPUT, NodeType.TEXT}
        for descendant in _collect_all_nodes(node)
    ):
        return False
    name = (node.name or "").lower()
    if any(token in name for token in ("back", "close", "nav", "arrow")):
        return True
    top = node.stack_placement.top if node.stack_placement.top is not None else node.offset_y
    vector_children = [
        child
        for child in node.children
        if child.type == NodeType.VECTOR and child.vector_asset_key
    ]
    return top is not None and top < 120 and bool(vector_children)


def _is_ambient_background_child(node: CleanDesignTreeNode) -> bool:
    if _subtree_has_interactive_ui(node):
        return False
    if _is_navigation_chrome_stack(node):
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


def render_ambient_decorative_node(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = NodeType.STACK,
) -> str | None:
    """Render a decorative vector/image subtree without the full layout pipeline.

    Ambient layers must not call ``render_node_body`` (buttons, theme tokens, inputs).
    """
    if node.type == NodeType.VECTOR and node.vector_asset_key:
        widget = _render_exported_vector(node, uses_svg=uses_svg)
        if widget is None:
            return None
        return _apply_stack_position(node, widget, parent_type=parent_type)

    if node.type == NodeType.IMAGE and node.image_asset_key:
        widget = _render_exported_vector(node, uses_svg=uses_svg)
        if widget is None:
            return None
        return _apply_stack_position(node, widget, parent_type=parent_type)

    if node.type == NodeType.STACK:
        parts: list[str] = []
        for child in node.children:
            rendered = render_ambient_decorative_node(
                child,
                uses_svg=uses_svg,
                parent_type=NodeType.STACK,
            )
            if rendered:
                parts.append(rendered)
        if not parts:
            return None
        inner = f"Stack(clipBehavior: Clip.none, children: [{', '.join(parts)}])"
        return _apply_stack_position(node, inner, parent_type=parent_type)

    return None


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


_TRANSPARENT_FILLS = frozenset({"0XFFFFFFFF", "0X00000000", None})


def _ambient_canvas_fill_expr(root: CleanDesignTreeNode) -> str | None:
    """Decorative vector fills belong in SVG layers, not a full-canvas ``ColoredBox``."""
    del root
    return None


def resolve_screen_canvas_background_expr(root: CleanDesignTreeNode) -> str | None:
    """Derive scaffold fill from the root frame only (not decorative ambient blobs)."""
    root_color = root.style.background_color
    if root_color and root_color.upper() not in _TRANSPARENT_FILLS:
        return dart_color_expr(root.style)
    return None


def patch_scaffold_background_from_tree(
    screen_code: str,
    root: CleanDesignTreeNode,
) -> str:
    """Align ``Scaffold`` background with the design canvas color from the tree."""
    fill_expr = resolve_screen_canvas_background_expr(root)
    if fill_expr is None:
        return screen_code
    if fill_expr.replace("const ", "") in screen_code:
        return screen_code
    updated, count = re.subn(
        r"backgroundColor:\s*const Color\(0xFFFFFFFF\)",
        f"backgroundColor: {fill_expr}",
        screen_code,
        count=1,
    )
    if count:
        return updated
    scaffold_match = re.search(
        r"(Scaffold\s*\([^)]*backgroundColor:\s*)([^,]+)",
        screen_code,
        re.DOTALL,
    )
    if scaffold_match is None:
        return screen_code
    return (
        screen_code[: scaffold_match.start(2)]
        + fill_expr
        + screen_code[scaffold_match.end(2) :]
    )


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
    bodies: list[str] = []
    for child in children:
        rendered = render_ambient_decorative_node(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
        )
        if rendered:
            bodies.append(rendered)
    if not bodies:
        return None
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    stack_inner = (
        "Stack(\n"
        "                              clipBehavior: Clip.none,\n"
        f"                              children: [{', '.join(bodies)}],\n"
        "                            )"
    )
    return (
        "Positioned.fill(\n"
        "                    child: IgnorePointer(\n"
        "                      child: Center(\n"
        "                        child: FittedBox(\n"
        "                          fit: BoxFit.scaleDown,\n"
        "                          child: SizedBox(\n"
        f"                            width: {width_token},\n"
        f"                            height: {height_token},\n"
        f"                            child: {stack_inner},\n"
        "                          ),\n"
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
                        screen_code[:child_start]
                        + "Stack(\n"
                        "          fit: StackFit.expand,\n"
                        "          children: [\n"
                        f"            {ambient_layer},\n"
                        f"            {foreground},\n"
                        "          ],\n"
                        "        )"
                        + screen_code[child_close + 1 :]
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
                    screen_code[:body_start]
                    + "Stack(\n"
                    "          fit: StackFit.expand,\n"
                    "          children: [\n"
                    f"            {ambient_layer},\n"
                    f"            {foreground},\n"
                    "          ],\n"
                    "        )"
                    + screen_code[body_close + 1 :]
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
        from figma_flutter_agent.generator.llm_dart import repair_dart_delimiters

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
    box_inner = block[box_open:box_close + 1]
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
        "                      child: Center(\n"
        "                        child: FittedBox(\n"
        "                          fit: BoxFit.scaleDown,\n"
        "                          child: SizedBox(\n"
        f"                            width: {width_token},\n"
        f"                            height: {height_token},\n"
        f"                            child: {stack_widget},\n"
        "                          ),\n"
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
        "BoxFit.contain" in block or "BoxFit.scaleDown" in block
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

    if expand_match is not None:
        direct_children = _iter_direct_stack_children_blocks(screen_code, list_open, list_close)
        if any(
            _is_ambient_cover_block(block.strip().rstrip(","))
            for _start, _end, block in direct_children
        ):
            return screen_code

    merged_stack_children: list[str] = []
    foreground_parts: list[str] = []
    for _start, _end, block in _iter_direct_stack_children_blocks(screen_code, list_open, list_close):
        stripped = block.strip().rstrip(",")
        if _CENTERED_FOREGROUND_LAYER_RE.match(stripped):
            return screen_code
        if _is_responsive_layout_builder_foreground(stripped):
            from figma_flutter_agent.generator.dart_layout_extract import (
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
