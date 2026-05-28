"""Figma node id anchors in generated Dart (ValueKey + optional comments)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.generator.dart_delimiters import find_matching_bracket as _find_matching_bracket
from figma_flutter_agent.generator.llm_dart import _find_matching_paren
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    NodeType,
    StackPlacement,
)

_POSITIONED_RE = re.compile(
    r"Positioned\s*\(\s*(?P<args>.*?)\s*,\s*child:\s*",
    re.DOTALL,
)
_BACKGROUND_WIDGET_RE = re.compile(r"(?:const\s+)?\w*Background\w*\s*\(")
_CONTENT_BODY_WIDGET_RE = re.compile(
    r"\b(?:const\s+)?\w*(?:MainContent|ScreenBody|FormBody)\w*\s*\(",
)


def _normalize_layout_block_for_screen_embed(block: str) -> str:
    """Inline layout ``textScaler`` locals when splicing blocks into a screen ``build``."""
    if "textScaler: textScaler" not in block:
        return block
    return block.replace(
        "textScaler: textScaler",
        "textScaler: MediaQuery.textScalerOf(context)",
    )


@dataclass(frozen=True)
class PositionedAnchor:
    """One positioned widget anchor in design coordinates."""

    node_id: str
    left: float
    top: float


def figma_key_token(node_id: str) -> str:
    """Return the Dart ``ValueKey`` token suffix for a Figma node id."""
    safe = node_id.replace(":", "_").replace("'", r"\'")
    return f"figma-{safe}"


def figma_value_key_arg(node_id: str) -> str:
    """Return a Dart named argument for ``ValueKey`` tied to ``node_id``."""
    return f"key: ValueKey('{figma_key_token(node_id)}')"


def collect_positioned_anchors(root: CleanDesignTreeNode) -> list[PositionedAnchor]:
    """Collect nodes that have stack placement (candidates for ``Positioned``)."""

    anchors: list[PositionedAnchor] = []

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if placement is not None:
            box = _placement_box(placement)
            if box is not None:
                left, top, _width, _height = box
                anchors.append(PositionedAnchor(node_id=node.id, left=left, top=top))
        for child in node.children:
            walk(child)

    walk(root)
    return anchors


def _placement_box(placement: StackPlacement) -> tuple[float, float, float, float] | None:
    width = placement.width
    height = placement.height
    if width is None or height is None:
        return None
    return placement.left, placement.top, width, height


def _coords_in_args(args: str, left: float, top: float, *, tolerance: float = 0.6) -> bool:
    left_match = re.search(r"left:\s*([\d.]+)", args)
    top_match = re.search(r"top:\s*([\d.]+)", args)
    if left_match is None or top_match is None:
        return False
    return abs(float(left_match.group(1)) - left) <= tolerance and abs(
        float(top_match.group(1)) - top
    ) <= tolerance


def inject_figma_keys_into_screen(screen_code: str, root: CleanDesignTreeNode) -> str:
    """Insert ``ValueKey('figma-…')`` into ``Positioned`` widgets matching tree placement.

    Args:
        screen_code: Screen Dart source (LLM or deterministic).
        root: Clean design tree for coordinate matching.

    Returns:
        Updated Dart source (unchanged when no anchors match).
    """
    anchors = collect_positioned_anchors(root)
    if not anchors:
        return screen_code

    updated = screen_code
    for anchor in anchors:
        if figma_key_token(anchor.node_id) in updated:
            continue

        def _inject(match: re.Match[str]) -> str:
            args = match.group("args")
            if not _coords_in_args(args, anchor.left, anchor.top):
                return match.group(0)
            if "key:" in args:
                return match.group(0)
            key = figma_value_key_arg(anchor.node_id)
            return f"Positioned({args}, {key}, child: "

        updated = _POSITIONED_RE.sub(_inject, updated, count=1)
    return updated


def _figma_key_present(source: str, node_id: str) -> bool:
    """Return True when ``source`` already references ``node_id`` as a Figma anchor."""
    token = figma_key_token(node_id)
    colon_token = f"figma-{node_id}"
    underscore_id = node_id.replace(":", "_")
    return token in source or colon_token in source or underscore_id in source


def _subtree_text_copies(node: CleanDesignTreeNode) -> tuple[str, ...]:
    copies: list[str] = []
    if node.type == NodeType.TEXT:
        text = (node.text or "").strip()
        if text:
            copies.append(text)
    for child in node.children:
        copies.extend(_subtree_text_copies(child))
    return tuple(copies)


def _text_copy_present(copy: str, source: str) -> bool:
    if not copy:
        return False
    if f"'{copy}'" in source or f'"{copy}"' in source:
        return True
    return f"label: '{copy}'" in source or f'label: "{copy}"' in source


def _layout_node_covered_in_sources(
    node_id: str,
    node: CleanDesignTreeNode | None,
    *sources: str,
) -> bool:
    """Return True when Figma anchors or label copy already exist in companion Dart."""
    combined = "\n".join(sources)
    if _figma_key_present(combined, node_id):
        return True
    if node is None:
        return False
    return any(_text_copy_present(copy, combined) for copy in _subtree_text_copies(node))


def _layout_node_covered_in_companion_sources(
    node_id: str,
    node: CleanDesignTreeNode | None,
    *companion_sources: str,
) -> bool:
    """Return True when extracted widgets already own this node (not the screen stub)."""
    if not companion_sources:
        return False
    return _layout_node_covered_in_sources(node_id, node, *companion_sources)


def companion_dart_sources_for_layout_inject(
    planned_files: dict[str, str],
    *,
    layout_path: str | None = None,
    generation: FlutterGenerationResponse | None = None,
) -> tuple[str, ...]:
    """Collect widget / feature Dart bodies used to detect LLM coverage before layout inject."""
    sources: list[str] = []
    for path, content in planned_files.items():
        if not path.endswith(".dart"):
            continue
        if layout_path and path.replace("\\", "/") == layout_path.replace("\\", "/"):
            continue
        normalized = path.replace("\\", "/")
        if normalized.startswith(("lib/widgets/", "lib/features/")):
            sources.append(content)
    if generation is not None:
        sources.extend(widget.code for widget in generation.extracted_widgets if widget.code)
    return tuple(sources)


def _find_node_by_id(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node_by_id(child, node_id)
        if found is not None:
            return found
    return None


def _extract_positioned_block(layout_code: str, node_id: str) -> str | None:
    """Return the ``Positioned(...)`` subtree for ``node_id`` from deterministic layout Dart."""
    variants = (
        f"ValueKey('{figma_key_token(node_id)}')",
        f"ValueKey('{node_id}')",
        f"figma-{node_id}",
        figma_key_token(node_id),
    )
    key_index = -1
    for variant in variants:
        key_index = layout_code.find(variant)
        if key_index >= 0:
            break
    if key_index < 0:
        return None
    pos_index = layout_code.rfind("Positioned(", 0, key_index)
    if pos_index < 0:
        return None
    paren_start = layout_code.find("(", pos_index)
    paren_end = _find_matching_paren(layout_code, paren_start)
    if paren_end is None:
        return None
    return layout_code[pos_index : paren_end + 1]


def _positioned_top(block: str) -> float:
    match = re.search(r"top:\s*([\d.]+)", block)
    if match is None:
        return 0.0
    return float(match.group(1))


def _design_stack_children_bounds(screen_code: str) -> tuple[int, int] | None:
    """Return insert bounds ``(after_open, before_close)`` for the main screen ``Stack`` children."""
    contain_matches = list(
        re.finditer(r"FittedBox\s*\(\s*fit:\s*BoxFit\.contain", screen_code)
    )
    search_region = screen_code
    if contain_matches:
        search_region = screen_code[contain_matches[-1].start() :]
    stack_match = re.search(r"child:\s*Stack\s*\(", search_region)
    if stack_match is not None:
        stack_open = search_region.find("(", stack_match.end() - 1)
        if stack_open >= 0:
            absolute_open = (
                contain_matches[-1].start() + stack_open
                if contain_matches
                else stack_open
            )
            stack_close = _find_matching_paren(screen_code, absolute_open)
            if stack_close is not None:
                children_label = screen_code.find("children: [", absolute_open, stack_close)
                if children_label >= 0:
                    list_open = screen_code.find("[", children_label)
                    list_close = _find_matching_bracket(screen_code, list_open, "[", "]")
                    if list_close is not None:
                        return list_open + 1, list_close

    key_match = re.search(r"ValueKey\(['\"]figma[-_:0-9]+['\"]\)", screen_code)
    if key_match is None:
        return None
    anchor_index = key_match.start()
    children_label = screen_code.rfind("children: [", 0, anchor_index)
    if children_label < 0:
        return None
    list_open = screen_code.find("[", children_label)
    list_close = _find_matching_bracket(screen_code, list_open, "[", "]")
    if list_close is None:
        return None
    return list_open + 1, list_close


def _collect_button_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.BUTTON and node.stack_placement is not None:
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _subtree_has_vector(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.VECTOR and node.vector_asset_key:
        return True
    return any(_subtree_has_vector(child) for child in node.children)


def _collect_chrome_stack_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if (
            node.type == NodeType.STACK
            and placement is not None
            and placement.width is not None
            and placement.height is not None
            and placement.width <= 72
            and placement.height <= 72
            and placement.top < 120
            and _subtree_has_vector(node)
        ):
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _collect_text_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if (
            node.type == NodeType.TEXT
            and node.stack_placement is not None
            and (node.text or "").strip()
        ):
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _collect_decorative_vector_node_ids(root: CleanDesignTreeNode) -> list[str]:
    """Absolute vector overlays eligible for layout inject when widgets own chrome."""
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.VECTOR and node.stack_placement is not None:
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _collect_layout_injectable_node_ids(
    root: CleanDesignTreeNode,
    *,
    decorative_only: bool = False,
) -> list[str]:
    """Node ids eligible for layout Positioned injection."""
    seen: set[str] = set()
    ordered: list[str] = []
    if decorative_only:
        candidates = (
            *_collect_chrome_stack_node_ids(root),
            *_collect_decorative_vector_node_ids(root),
        )
    else:
        candidates = (
            *_collect_button_node_ids(root),
            *_collect_text_node_ids(root),
            *_collect_chrome_stack_node_ids(root),
        )
    for node_id in candidates:
        if node_id in seen:
            continue
        seen.add(node_id)
        ordered.append(node_id)
    return ordered


_LAYOUT_CHROME_MARKERS = ("BoxShape.circle", "border: Border.all")

_LAYOUT_COMPLEXITY_TOKENS = (
    "Container(",
    "Stack(",
    "SvgPicture",
    "BoxDecoration",
    "Material(",
    "InkWell(",
    "border:",
)


def _layout_subtree_complexity(block: str) -> int:
    return sum(block.count(token) for token in _LAYOUT_COMPLEXITY_TOKENS)


def _positioned_block_needs_layout_upgrade(
    screen_block: str,
    layout_block: str,
) -> bool:
    layout_score = _layout_subtree_complexity(layout_block)
    screen_score = _layout_subtree_complexity(screen_block)
    if layout_score >= screen_score + 2:
        return True
    for marker in _LAYOUT_CHROME_MARKERS:
        if marker in layout_block and marker not in screen_block:
            return True
    if re.search(
        r"\b(?:Outlined|Filled|Elevated|Text)Button\s*\(",
        screen_block,
    ) and not re.search(
        r"\b(?:Outlined|Filled|Elevated|Text)Button\s*\(",
        layout_block,
    ):
        if layout_score > screen_score:
            return True
    return False


def _finalize_spliced_dart_fragment(
    prior: str,
    candidate: str,
    *,
    label: str,
) -> str:
    """Trim splice output and reject it when bracket balance is broken."""
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    trimmed = candidate.strip()
    if trimmed == prior.strip():
        return prior
    delimiter_error = validate_dart_delimiters(trimmed)
    if delimiter_error is None:
        return trimmed
    logger.warning(
        "{} splice broke Dart delimiters ({}); keeping prior screenCode",
        label,
        delimiter_error,
    )
    return prior


def _replace_positioned_block(screen_code: str, old_block: str, new_block: str) -> str:
    index = screen_code.find(old_block)
    if index < 0:
        return screen_code
    candidate = screen_code[:index] + new_block.strip() + screen_code[index + len(old_block) :]
    return _finalize_spliced_dart_fragment(
        screen_code,
        candidate,
        label="layout Positioned block replace",
    )


def upgrade_incomplete_layout_positioned(
    screen_code: str,
    layout_code: str,
    root: CleanDesignTreeNode,
    *,
    companion_sources: tuple[str, ...] = (),
) -> str:
    """Replace simplified LLM chrome with full deterministic layout subtrees."""
    updated = screen_code
    for node_id in _collect_layout_upgrade_node_ids(root):
        node = _find_node_by_id(root, node_id)
        if _layout_node_covered_in_companion_sources(node_id, node, *companion_sources):
            continue
        if not _figma_key_present(updated, node_id):
            continue
        layout_block = _extract_positioned_block(layout_code, node_id)
        screen_block = _extract_positioned_block(updated, node_id)
        if layout_block is None or screen_block is None:
            continue
        if not _positioned_block_needs_layout_upgrade(screen_block, layout_block):
            continue
        layout_block = _normalize_layout_block_for_screen_embed(layout_block)
        candidate = _replace_positioned_block(updated, screen_block, layout_block)
        if candidate == updated:
            continue
        updated = candidate
        logger.info(
            "Upgraded incomplete layout Positioned for node {}",
            node_id,
        )
    return updated


def _collect_layout_upgrade_node_ids(root: CleanDesignTreeNode) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for node_id in (
        *_collect_button_node_ids(root),
        *_collect_chrome_stack_node_ids(root),
    ):
        if node_id in seen:
            continue
        seen.add(node_id)
        ordered.append(node_id)
    return ordered


def _layout_inject_suppressed_for_content_widget(
    screen_code: str,
    companion_sources: tuple[str, ...],
) -> bool:
    """Skip layout inject when the screen delegates UI to an extracted content widget."""
    del companion_sources
    return _CONTENT_BODY_WIDGET_RE.search(screen_code) is not None


def inject_missing_layout_positioned(
    screen_code: str,
    layout_code: str,
    root: CleanDesignTreeNode,
    *,
    companion_sources: tuple[str, ...] = (),
) -> str:
    """Splice deterministic ``Positioned`` widgets omitted from LLM ``screenCode``.

    When the LLM skips a ``BUTTON`` or link ``TEXT`` node that deterministic layout
    already rendered, copy the matching ``Positioned`` block from
    ``lib/generated/{feature}_layout.dart`` into the screen body.

    Args:
        screen_code: LLM screen ``build`` body source.
        layout_code: Deterministic layout file contents for the same feature.
        root: Clean design tree for node ids and vertical ordering.
        companion_sources: Additional Dart sources (extracted widgets, planned widget
            files) searched for existing Figma keys and visible copy before injecting.

    Returns:
        Updated screen Dart source.
    """
    if _layout_inject_suppressed_for_content_widget(screen_code, companion_sources):
        logger.info(
            "Skipping layout Positioned inject/upgrade: screen delegates body to content widget"
        )
        return screen_code
    decorative_only = bool(companion_sources)
    screen_code = upgrade_incomplete_layout_positioned(
        screen_code,
        layout_code,
        root,
        companion_sources=companion_sources,
    )
    bounds = _design_stack_children_bounds(screen_code)
    if bounds is None:
        return screen_code
    insert_start, insert_end = bounds
    existing_segment = screen_code[insert_start:insert_end]
    coverage_sources = (screen_code, *companion_sources)
    to_insert: list[tuple[float, str]] = []
    for node_id in _collect_layout_injectable_node_ids(
        root,
        decorative_only=decorative_only,
    ):
        node = _find_node_by_id(root, node_id)
        if _layout_node_covered_in_sources(node_id, node, *coverage_sources):
            continue
        block = _extract_positioned_block(layout_code, node_id)
        if block is None:
            continue
        block = _normalize_layout_block_for_screen_embed(block)
        top = node.stack_placement.top if node and node.stack_placement else _positioned_top(block)
        to_insert.append((top, block))
        kind = node.type.value if node is not None else "node"
        logger.info(
            "Injected missing layout Positioned for {} node {} (top={})",
            kind,
            node_id,
            top,
        )
    if not to_insert:
        return screen_code
    existing_segment = _sanitize_stack_children_segment(existing_segment)
    ordered = sorted(to_insert, key=lambda item: item[0])
    missing_blocks = [block for _, block in ordered if block.strip()]
    code_to_inject = _format_positioned_injection_batch(missing_blocks)
    insert_at = _find_positioned_insert_index(existing_segment, ordered[0][0])
    updated_segment = _merge_segment_prefix_and_batch(
        existing_segment[:insert_at],
        code_to_inject,
        existing_segment[insert_at:],
    )
    candidate = screen_code[:insert_start] + updated_segment.strip() + screen_code[insert_end:]
    return _finalize_spliced_dart_fragment(
        screen_code,
        candidate,
        label="layout Positioned inject",
    )


def _sanitize_stack_children_segment(segment: str) -> str:
    """Drop orphan commas and blank lines from a ``children: [`` list body."""
    lines = segment.splitlines()
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == ",":
            continue
        filtered.append(line)
    updated = "\n".join(filtered).strip()
    while updated.startswith(","):
        updated = updated[1:].lstrip()
    while updated.endswith(","):
        updated = updated[:-1].rstrip()
    return updated


def _merge_segment_prefix_and_batch(prefix: str, batch: str, suffix: str) -> str:
    """Join list prefix, injected batch, and suffix without duplicate commas."""
    parts: list[str] = []
    head = prefix.rstrip()
    if head.endswith(","):
        head = head[:-1].rstrip()
    if head:
        parts.append(head)
    batch_body = batch.strip()
    if batch_body:
        parts.append(batch_body)
    tail = _sanitize_stack_children_segment(suffix)
    if tail:
        parts.append(tail)
    if not parts:
        return ""
    merged = ",\n".join(parts)
    if not merged.endswith("\n"):
        merged = f"{merged}\n"
    return merged


def _find_positioned_insert_index(segment: str, top: float) -> int:
    """Return the index in ``segment`` where a ``top``-sorted ``Positioned`` batch belongs."""
    insert_at = len(segment)
    for match in re.finditer(r"Positioned\s*\(", segment):
        existing_top = _positioned_top(segment[match.start() : match.start() + 240])
        if existing_top > top:
            insert_at = min(insert_at, match.start())
    return insert_at


def _format_positioned_injection_batch(blocks: list[str]) -> str:
    """Join injectable ``Positioned`` widgets with comma-newline separators."""
    lines: list[str] = []
    for block in blocks:
        stripped = block.strip().rstrip(",")
        if stripped:
            lines.append(f"                                  {stripped},")
    if not lines:
        return ""
    return ",\n".join(lines) + "\n"


def _inject_positioned_blocks_by_top(
    segment: str,
    to_insert: list[tuple[float, str]],
) -> str:
    """Insert sorted ``Positioned`` blocks into a ``children: [`` segment."""
    if not to_insert:
        return segment
    segment = _sanitize_stack_children_segment(segment)
    ordered = sorted(to_insert, key=lambda item: item[0])
    batch = _format_positioned_injection_batch([block for _, block in ordered])
    if not batch:
        return segment
    insert_at = _find_positioned_insert_index(segment, ordered[0][0])
    return _merge_segment_prefix_and_batch(
        segment[:insert_at],
        batch,
        segment[insert_at:],
    )


def _insert_positioned_by_top(segment: str, block: str, top: float) -> str:
    """Insert a single ``Positioned`` block into a ``children: [`` segment sorted by ``top``."""
    return _inject_positioned_blocks_by_top(segment, [(top, block)])


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
    if "Positioned.fill" in stripped and ("BoxFit.cover" in stripped or "BoxFit.fill" in stripped):
        return True
    return False


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
