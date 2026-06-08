"""Dart expression-end scanning helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_bracket,
    find_matching_paren,
)


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
    """Return the index after a Dart expression beginning at ``start``."""
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
