"""Dart delimiter validation, balancing, and repair utilities."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_paren as _find_matching_paren,
)


def _skip_dart_string(source: str, start: int) -> int:
    """Return the index after a Dart string literal starting at ``start``."""
    if start >= len(source):
        return start

    quote = source[start]
    if quote not in {"'", '"'}:
        return start

    triple = start + 2 < len(source) and source[start : start + 3] == quote * 3
    if triple:
        end_marker = quote * 3
        index = start + 3
        while index + 2 < len(source):
            if source[index : index + 3] == end_marker:
                return index + 3
            index += 1
        return len(source)

    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        index += 1
    return len(source)


def validate_dart_delimiters(source: str) -> str | None:
    """Return a human-readable error when brackets/parens/braces are unbalanced.

    Skips Dart comments and string literals so braces inside them do not affect
    the structural balance check.

    Args:
        source: Dart source fragment to inspect.

    Returns:
        Error message, or ``None`` when delimiters balance.
    """
    stack: list[tuple[str, int]] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    line_number = 1
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            line_number += 1
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                index += 2
                while index < length and source[index] != "\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < length:
                    if source[index] == "*" and source[index + 1] == "/":
                        index += 2
                        break
                    if source[index] == "\n":
                        line_number += 1
                    index += 1
                else:
                    index = length
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            index = _skip_dart_string(source, index + 1)
            continue

        if char in {"'", '"'}:
            index = _skip_dart_string(source, index)
            continue

        if char in pairs:
            stack.append((char, line_number))
            index += 1
            continue

        if char in closing:
            if not stack or stack[-1][0] != closing[char]:
                return f"Unexpected '{char}' near line {line_number}"
            stack.pop()
            index += 1
            continue

        index += 1

    if stack:
        opener, opener_line = stack[-1]
        return f"Unclosed '{opener}' opened near line {opener_line}"

    return None


def _dart_delimiter_stack(source: str) -> list[str] | None:
    """Return unmatched open delimiters, or ``None`` when closers are invalid."""
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                index += 2
                while index < length and source[index] != "\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < length:
                    if source[index] == "*" and source[index + 1] == "/":
                        index += 2
                        break
                    index += 1
                else:
                    index = length
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            index = _skip_dart_string(source, index + 1)
            continue

        if char in {"'", '"'}:
            index = _skip_dart_string(source, index)
            continue

        if char in pairs:
            stack.append(char)
            index += 1
            continue

        if char in closing:
            if not stack or stack[-1] != closing[char]:
                return None
            stack.pop()
            index += 1
            continue

        index += 1

    return stack


def balance_dart_delimiters(source: str) -> str | None:
    """Append missing ``)`` / ``]`` / ``}`` when the fragment only lacks closers.

    Args:
        source: Dart source fragment.

    Returns:
        Balanced source, or ``None`` when unexpected closers make auto-fix unsafe.
    """
    stack = _dart_delimiter_stack(source)
    if stack is None:
        return None
    if not stack:
        return source
    pairs = {"(": ")", "[": "]", "{": "}"}
    suffix = "".join(pairs[opener] for opener in reversed(stack))
    return f"{source.rstrip()}\n{suffix}\n"


def trim_surplus_dart_delimiters(source: str) -> str | None:
    """Drop stray ``)`` / ``]`` / ``}`` that do not match an opener.

    Args:
        source: Dart source fragment.

    Returns:
        Filtered source, or ``None`` when the scan cannot proceed safely.
    """
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    parts: list[str] = []
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char == "\n":
            parts.append(char)
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                line_end = source.find("\n", index)
                if line_end == -1:
                    parts.append(source[index:])
                    break
                parts.append(source[index:line_end])
                index = line_end
                continue
            if next_char == "*":
                block_end = index + 2
                while block_end + 1 < length:
                    if source[block_end] == "*" and source[block_end + 1] == "/":
                        block_end += 2
                        break
                    block_end += 1
                else:
                    block_end = length
                parts.append(source[index:block_end])
                index = block_end
                continue

        if char == "r" and index + 1 < length and source[index + 1] in {"'", '"'}:
            end = _skip_dart_string(source, index + 1)
            parts.append(source[index:end])
            index = end
            continue

        if char in {"'", '"'}:
            end = _skip_dart_string(source, index)
            parts.append(source[index:end])
            index = end
            continue

        if char in pairs:
            stack.append(char)
            parts.append(char)
            index += 1
            continue

        if char in closing:
            if stack and stack[-1] == closing[char]:
                stack.pop()
                parts.append(char)
            index += 1
            continue

        parts.append(char)
        index += 1

    return "".join(parts)


_CLASS_MEMBER_PREFIXES = (
    "const ",
    "final ",
    "var ",
    "@override",
    "@",
    "Widget ",
    "void ",
)


def _find_class_body_open_brace(source: str, header_index: int) -> int | None:
    """Return the ``{`` that opens a class body after the ``extends`` clause."""
    index = header_index
    length = len(source)
    generic_depth = 0

    while index < length:
        char = source[index]
        if char in " \t\r\n":
            index += 1
            continue

        if char == "/" and index + 1 < length:
            next_char = source[index + 1]
            if next_char == "/":
                index += 2
                while index < length and source[index] != "\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < length:
                    if source[index] == "*" and source[index + 1] == "/":
                        index += 2
                        break
                    index += 1
                else:
                    return None
                continue

        if generic_depth == 0 and char == "{":
            return index
        if char == "<":
            generic_depth += 1
            index += 1
            continue
        if char == ">":
            generic_depth = max(0, generic_depth - 1)
            index += 1
            continue
        if generic_depth == 0:
            if source.startswith("implements", index) or source.startswith(
                "with", index
            ):
                index += 1
                continue
            if any(
                source.startswith(prefix, index) for prefix in _CLASS_MEMBER_PREFIXES
            ):
                return None
        if char.isalpha() or char == "_" or char in {",", "."}:
            index += 1
            continue
        if generic_depth == 0:
            return None
        index += 1
    return None


def repair_dart_delimiters(source: str) -> str:
    """Best-effort delimiter repair: append missing closers, then trim surplus."""
    if validate_dart_delimiters(source) is None:
        return source

    balanced = balance_dart_delimiters(source)
    candidate = balanced if balanced is not None else source
    if validate_dart_delimiters(candidate) is None:
        return candidate

    trimmed = trim_surplus_dart_delimiters(candidate)
    if trimmed is not None:
        if validate_dart_delimiters(trimmed) is None:
            return trimmed
        balanced_trimmed = balance_dart_delimiters(trimmed)
        if balanced_trimmed is not None and validate_dart_delimiters(balanced_trimmed) is None:
            return balanced_trimmed

    from figma_flutter_agent.generator.dart.syntax_repairs import (
        fix_garbage_closers_after_link_rich,
    )

    link_fixed = fix_garbage_closers_after_link_rich(candidate)
    if link_fixed != candidate and validate_dart_delimiters(link_fixed) is None:
        return link_fixed

    return source
