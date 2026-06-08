"""Import normalization for generated Dart."""

from __future__ import annotations

import re
from pathlib import Path

APP_BREAKPOINTS_RE = re.compile(r"\bAppBreakpoints\b")
APP_LAYOUT_IMPORT_RE = re.compile(r"theme/app_layout\.dart")
PACKAGE_IMPORT_RE = re.compile(r"import\s+'package:([^/]+)/")
SELF_WIDGET_IMPORT_RE = re.compile(
    r"^\s*import\s+'package:[^']+/widgets/([^']+)\.dart';\s*$",
    re.MULTILINE,
)
DART_UI_IMPORT_RE = re.compile(r"import\s+['\"]dart:ui['\"](\s+show\s+([^;]+))?;")


def package_name_from_source(source: str, *, default: str = "demo_app") -> str:
    for match in PACKAGE_IMPORT_RE.finditer(source):
        package = match.group(1)
        if package != "flutter":
            return package
    return default


def ensure_app_layout_import(source: str, *, package_name: str | None = None) -> str:
    """Insert ``theme/app_layout.dart`` when generated code references ``AppBreakpoints``."""
    if not APP_BREAKPOINTS_RE.search(source):
        return source
    if APP_LAYOUT_IMPORT_RE.search(source):
        return source
    pkg = package_name or package_name_from_source(source)
    import_line = f"import 'package:{pkg}/theme/app_layout.dart';"
    material = "import 'package:flutter/material.dart';"
    if material in source:
        return source.replace(material, f"{material}\n{import_line}", 1)
    return f"{import_line}\n\n{source}" if source else import_line


def ensure_dart_ui_import(source: str) -> str:
    """Insert or extend ``dart:ui`` imports for blur and transform symbols."""
    needs_filter = "ImageFilter" in source or "BackdropFilter" in source
    needs_matrix = "Matrix4." in source
    if not needs_filter and not needs_matrix:
        return source

    required: set[str] = set()
    if needs_filter:
        required.add("ImageFilter")
    if needs_matrix:
        required.add("Matrix4")

    match = DART_UI_IMPORT_RE.search(source)
    if match is not None:
        show_clause = match.group(2)
        if show_clause is None:
            return source
        shown = {symbol.strip() for symbol in show_clause.split(",") if symbol.strip()}
        missing = required - shown
        if not missing:
            return source
        merged = ", ".join(sorted(shown | required))
        replacement = f"import 'dart:ui' show {merged};"
        return source[: match.start()] + replacement + source[match.end() :]

    import_line = f"import 'dart:ui' show {', '.join(sorted(required))};"
    material = "import 'package:flutter/material.dart';"
    if material in source:
        return source.replace(material, f"{material}\n{import_line}", 1)
    return f"{import_line}\n\n{source}" if source else import_line


def strip_self_widget_import(source: str, *, widget_path: str) -> str:
    """Remove a widget file importing itself (stale merge artifact)."""
    stem = Path(widget_path.replace("\\", "/")).stem

    def replacer(match: re.Match[str]) -> str:
        return "" if match.group(1) == stem else match.group(0)

    return SELF_WIDGET_IMPORT_RE.sub(replacer, source)
