"""Shared block-extraction helpers for ambient sync (matching parens/brackets, asset paths)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.llm_codegen import _find_matching_paren

_SVG_ASSET_RE = re.compile(r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_IMAGE_ASSET_RE = re.compile(r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")


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
