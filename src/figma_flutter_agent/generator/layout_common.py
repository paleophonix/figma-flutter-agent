"""Shared helpers for deterministic layout code generation."""

from __future__ import annotations

import re

LAZY_CHILD_THRESHOLD = 8

_SNAKE_CASE = re.compile(r"[^a-zA-Z0-9]+")


def to_snake_case(value: str) -> str:
    """Convert arbitrary text to snake_case."""
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    parts = [part for part in _SNAKE_CASE.split(normalized) if part]
    return "_".join(part.lower() for part in parts) or "feature"


def to_pascal_case(value: str) -> str:
    """Convert arbitrary text to PascalCase."""
    parts = [part for part in _SNAKE_CASE.split(value) if part]
    return "".join(part.capitalize() for part in parts) or "Feature"


def to_camel_case(value: str) -> str:
    """Convert arbitrary text to lowerCamelCase."""
    pascal = to_pascal_case(value)
    return pascal[0].lower() + pascal[1:] if len(pascal) > 1 else pascal.lower()


def escape_dart_string(value: str) -> str:
    """Escape a string for single-quoted Dart literals."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\\", "\\\\").replace("\n", "\\n").replace("'", "\\'")


def wrap_repaint_boundary(widget: str) -> str:
    """Isolate repaint for scrollable or heavy subtrees (spec §15)."""
    return f"RepaintBoundary(child: {widget})"
