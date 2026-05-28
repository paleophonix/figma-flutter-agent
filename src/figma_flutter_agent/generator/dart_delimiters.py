"""Bracket/paren matching for non-AST Dart helpers outside ``dart_postprocess``.

Structural layout transforms belong in ``figma_flutter_agent.tools.ast_sidecar``.
"""

from __future__ import annotations


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
