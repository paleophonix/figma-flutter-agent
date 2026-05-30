"""Bracket/paren matching for non-AST Dart helpers outside ``dart_postprocess``.

Structural layout transforms belong in ``figma_flutter_agent.tools.ast_sidecar``.
"""

from __future__ import annotations

import re


def find_matching_paren(source: str, open_index: int) -> int | None:
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


def find_balanced_call_close_paren(source: str, open_index: int) -> int | None:
    """Close ``)`` for a call/list that may contain ``() {}`` closure literals in arguments."""
    if open_index >= len(source) or source[open_index] != "(":
        return None

    paren_depth = 0
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
            paren_depth += 1
            continue
        if char == ")":
            paren_depth -= 1
            if paren_depth == 0:
                return index
    return None


def skip_dart_expression(source: str, start: int) -> int:
    """Return index after one top-level Dart expression starting at ``start``."""
    index = start
    length = len(source)
    while index < length and source[index].isspace():
        index += 1
    if index >= length:
        return index

    if source.startswith("const ", index):
        index += len("const ")

    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    in_string = False
    string_quote = ""
    escape = False

    while index < length:
        char = source[index]
        if in_string:
            if escape:
                escape = False
                index += 1
                continue
            if char == "\\":
                escape = True
                index += 1
                continue
            if char == string_quote:
                in_string = False
            index += 1
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            index += 1
            continue
        if char == "(":
            paren_depth += 1
            index += 1
            continue
        if char == ")":
            if paren_depth > 0:
                paren_depth -= 1
                index += 1
                continue
            break
        if char == "[":
            bracket_depth += 1
            index += 1
            continue
        if char == "]":
            if bracket_depth > 0:
                bracket_depth -= 1
                index += 1
                continue
            break
        if char == "{":
            brace_depth += 1
            index += 1
            continue
        if char == "}":
            if brace_depth > 0:
                brace_depth -= 1
                index += 1
                continue
            break
        if char == "," and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
            break
        index += 1
    return index


def replace_first_copywith_color(source: str, color_expr: str) -> tuple[str, bool]:
    """Replace the first ``copyWith`` ``color:`` value, including nested ``Color(...)``."""
    marker = "copyWith("
    marker_index = source.find(marker)
    if marker_index == -1:
        return source, False
    open_paren = marker_index + len(marker) - 1
    close_paren = find_matching_paren(source, open_paren)
    if close_paren is None:
        return source, False
    inner_start = open_paren + 1
    inner = source[inner_start:close_paren]
    color_match = re.search(r"\bcolor:\s*", inner)
    if color_match is None:
        return source, False
    value_start = color_match.end()
    value_end = skip_dart_expression(inner, value_start)
    new_inner = (
        inner[: color_match.start()]
        + f"color: {color_expr}"
        + inner[value_end:]
    )
    return source[:inner_start] + new_inner + source[close_paren:], True


def find_matching_paren_backwards(source: str, close_index: int) -> int | None:
    if close_index >= len(source) or source[close_index] != ")":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(close_index, -1, -1):
        char = source[index]
        if in_string:
            if index > 0 and source[index - 1] == "\\":
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == ")":
            depth += 1
            continue
        if char == "(":
            depth -= 1
            if depth == 0:
                return index
    return None


def find_matching_bracket(
    source: str,
    open_index: int,
    open_char: str,
    close_char: str,
) -> int | None:
    if open_index >= len(source) or source[open_index] != open_char:
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
        if char == open_char:
            depth += 1
            continue
        if char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def find_matching_brace(source: str, open_index: int) -> int | None:
    return find_matching_bracket(source, open_index, "{", "}")


def find_enclosing_brace_open(source: str, index: int) -> int | None:
    depth = 0
    for position in range(index - 1, -1, -1):
        char = source[position]
        if char == "}":
            depth += 1
            continue
        if char != "{":
            continue
        if depth == 0:
            return position
        depth -= 1
    return None


def _string_literal_end(source: str, start: int) -> int | None:
    if start >= len(source) or source[start] not in {"'", '"'}:
        return None
    quote = source[start]
    escape = False
    for index in range(start + 1, len(source)):
        char = source[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == quote:
            return index + 1
    return None


def _extend_trailing_function_body(source: str, value_end: int) -> int:
    tail = value_end
    while tail < len(source) and source[tail].isspace():
        tail += 1
    if tail < len(source) and source[tail] == "{":
        close_index = find_matching_bracket(source, tail, "{", "}")
        if close_index is not None:
            return close_index + 1
    return value_end


def find_expression_end(source: str, start: int) -> int | None:
    """Return the index after a Dart expression beginning at ``start`` (layout extract only)."""
    index = start
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source):
        return index

    if source.startswith("const ", index):
        index += len("const ")
        while index < len(source) and source[index].isspace():
            index += 1

    char = source[index]
    if char == "(":
        close_index = find_matching_paren(source, index)
        if close_index is None:
            return None
        return _extend_trailing_function_body(source, close_index + 1)
    if char == "[":
        close_index = find_matching_bracket(source, index, "[", "]")
        return None if close_index is None else close_index + 1
    if char == "{":
        close_index = find_matching_bracket(source, index, "{", "}")
        return None if close_index is None else close_index + 1
    if char in {"'", '"'}:
        return _string_literal_end(source, index)

    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    for position in range(index, len(source)):
        char_at = source[position]
        if in_string:
            if escape:
                escape = False
                continue
            if char_at == "\\":
                escape = True
                continue
            if char_at == string_quote:
                in_string = False
            continue

        if char_at in {"'", '"'}:
            in_string = True
            string_quote = char_at
            continue
        if char_at == "(":
            depth += 1
            continue
        if char_at == ")":
            if depth == 0:
                return position
            depth -= 1
            continue
        if char_at == "," and depth == 0:
            return position
    return len(source)
