"""Dart Positioned block extraction and splice helpers."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_bracket as _find_matching_bracket,
)
from figma_flutter_agent.generator.dart.llm_codegen import _find_matching_paren
from figma_flutter_agent.generator.figma_anchor.keys import (
    figma_key_token,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
)

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
    contain_matches = list(re.finditer(r"FittedBox\s*\(\s*fit:\s*BoxFit\.contain", screen_code))
    search_region = screen_code
    if contain_matches:
        search_region = screen_code[contain_matches[-1].start() :]
    stack_match = re.search(r"child:\s*Stack\s*\(", search_region)
    if stack_match is not None:
        stack_open = search_region.find("(", stack_match.end() - 1)
        if stack_open >= 0:
            absolute_open = (
                contain_matches[-1].start() + stack_open if contain_matches else stack_open
            )
            stack_close = _find_matching_paren(screen_code, absolute_open)
            if stack_close is not None:
                children_label = screen_code.find("children: [", absolute_open, stack_close)
                if children_label >= 0:
                    list_open = screen_code.find("[", children_label)
                    list_close = _find_matching_bracket(screen_code, list_open, "[", "]")
                    if list_close is not None:
                        return list_open + 1, list_close

    key_match = re.search(r"ValueKey\(['\"]figma[A-Za-z0-9_:-]*['\"]\)", screen_code)
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
    return bool(
        re.search(
            r"\b(?:Outlined|Filled|Elevated|Text)Button\s*\(",
            screen_block,
        )
        and not re.search(
            r"\b(?:Outlined|Filled|Elevated|Text)Button\s*\(",
            layout_block,
        )
        and layout_score > screen_score
    )


def _finalize_spliced_dart_fragment(
    prior: str,
    candidate: str,
    *,
    label: str,
) -> str:
    """Trim splice output and reject it when bracket balance is broken."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

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
