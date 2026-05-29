"""Lightweight Dart syntax repairs without ast_sidecar imports."""

from __future__ import annotations

import re

_DUPLICATE_CHILD_PARAM_RE = re.compile(r"(\bchild:\s*)+child:\s*", re.IGNORECASE)
_MISPLACED_CHILD_BEFORE_NAMED_RE = re.compile(
    r"\bchild:\s+(?=(?:key|onPressed|backgroundColor|textColor|text|icon|border|required|super)\b\s*:)",
    re.IGNORECASE,
)
_GARBAGE_CLOSER_ONLY_LINE = re.compile(r"^[\]\)\}]{2,}$")
_ORPHAN_SEMICOLON_LINE = re.compile(r"^;+\s*$")
_FORMAT_ERROR_LINE_RE = re.compile(r"^line (\d+), column \d+ of ")
_DUPLICATE_KEY_AFTER_SUPER_RE = re.compile(
    r"(\bsuper\.key\s*,\s*)(?:Key\?\s+key\s*=\s*null|Key\s+key)\s*,\s*",
    re.MULTILINE,
)
_DUPLICATE_KEY_TRAILING_IN_SUPER_CTOR_RE = re.compile(
    r"(\{[^{}]*\bsuper\.key\b[^{}]*),\s*Key\?\s+key(?:\s*=\s*null)?\s*(\})",
)
_TEXT_OPENER_RE = re.compile(r"(?<![A-Za-z0-9_])(const\s+)?Text\s*\(")
_DESIGN_CANVAS_FITTED_CONTAIN_RE = re.compile(
    r"FittedBox\(\s*fit:\s*BoxFit\.contain,\s*child:\s*SizedBox\s*\("
)
_ELEVATED_BUTTON_OPENER_RE = re.compile(r"(?<![A-Za-z0-9_])ElevatedButton\s*\(")
_LIGHT_ELEVATED_BUTTON_BG_RE = re.compile(
    r"backgroundColor:\s*(?:const\s+)?Color\(0x(?:FF)?(?:FFFFFF|F2F3F7|EBEAEC|E6E6E6|FAF8F5)\)",
    re.IGNORECASE,
)
_TEXT_STYLE_BLACK_RE = re.compile(r"style:\s*TextStyle\([^)]*color:\s*Color\(0xFF000000\)")
_TEXT_STYLE_ONLY_PARAMS = frozenset(
    {
        "fontSize",
        "fontWeight",
        "letterSpacing",
        "fontFamily",
        "fontFamilyFallback",
        "color",
        "height",
        "decoration",
        "decorationColor",
        "decorationStyle",
        "fontStyle",
        "leadingDistribution",
        "wordSpacing",
        "backgroundColor",
        "foreground",
        "background",
        "shadows",
    }
)
_CONST_APP_TYPO_COPY_WITH_RE = re.compile(
    r"\bconst\s+(AppTypography\.\w+\.copyWith\()",
)
_CONST_APP_TYPO_TOKEN_RE = re.compile(r"\bconst\s+(AppTypography\.\w+)\b")
_ORPHAN_FONT_FALLBACK_LINE_RE = re.compile(
    r"^[ \t]*'[^']+',[ \t]*'[^']+'\],[ \t]*\r?\n",
    re.MULTILINE,
)


def collapse_duplicate_child_named_params(source: str) -> str:
    """Collapse LLM stutter ``child: child: …`` into a single ``child:``."""
    updated = source
    while True:
        collapsed = _DUPLICATE_CHILD_PARAM_RE.sub("child: ", updated)
        if collapsed == updated:
            return updated
        updated = collapsed


def fix_misplaced_child_before_named_params(source: str) -> str:
    """Rewrite LLM ``child: key:`` / ``child: onPressed:`` stutter to valid named params."""
    return _MISPLACED_CHILD_BEFORE_NAMED_RE.sub("", source)


def is_garbage_closer_only_line(line: str) -> bool:
    """True when a physical line is only stray ``)`` / ``]`` / ``}`` (LLM delimiter avalanche)."""
    stripped = line.strip()
    return bool(stripped) and _GARBAGE_CLOSER_ONLY_LINE.fullmatch(stripped) is not None


def is_orphan_semicolon_line(line: str) -> bool:
    """True when a line is only ``;`` (delimiter repair drift)."""
    return _ORPHAN_SEMICOLON_LINE.match(line.strip()) is not None


def strip_orphan_semicolon_only_lines(source: str) -> str:
    """Drop lines that contain only a semicolon."""
    lines = source.splitlines()
    if not any(is_orphan_semicolon_line(line) for line in lines):
        return source
    return "\n".join(line for line in lines if not is_orphan_semicolon_line(line))


def normalize_app_typography_style_references(source: str) -> str:
    """Fix ``const AppTypography.token`` (invalid ctor) and orphan fallback list shards."""
    updated = _CONST_APP_TYPO_COPY_WITH_RE.sub(r"\1", source)
    updated = _CONST_APP_TYPO_TOKEN_RE.sub(r"\1", updated)
    return _ORPHAN_FONT_FALLBACK_LINE_RE.sub("", updated)


def strip_duplicate_key_after_super(source: str) -> str:
    """Remove ``Key? key = null`` when ``super.key`` is already present."""
    updated = _DUPLICATE_KEY_AFTER_SUPER_RE.sub(r"\1", source)
    return _DUPLICATE_KEY_TRAILING_IN_SUPER_CTOR_RE.sub(r"\1\2", updated)


def _iter_top_level_call_args(inner: str):
    """Yield ``(param_name, value_start, value_end)`` for each top-level argument."""
    from figma_flutter_agent.generator.dart_delimiters import find_expression_end

    index = 0
    length = len(inner)
    while index < length:
        while index < length and inner[index] in " \t\n\r,":
            index += 1
        if index >= length:
            break
        param_name = None
        cursor = index
        if inner[cursor] not in {"'", '"'}:
            named = re.match(r"([A-Za-z_]\w*)\s*:", inner[cursor:])
            if named is not None:
                param_name = named.group(1)
                cursor += named.end()
        while cursor < length and inner[cursor].isspace():
            cursor += 1
        value_end = find_expression_end(inner, cursor)
        if value_end is None:
            break
        yield param_name, index, value_end
        index = value_end


def _merge_misplaced_into_existing_style(
    inner: str,
    args: list[tuple[str | None, int, int]],
    misplaced: list[tuple[str | None, int, int]],
) -> str | None:
    """Fold orphan ``fontSize:`` / … args into an existing ``style: TextStyle(...)``."""
    from figma_flutter_agent.generator.dart_delimiters import find_matching_paren

    style_arg = next((item for item in args if item[0] == "style"), None)
    if style_arg is None:
        return None
    _, style_start, style_end = style_arg
    style_value = inner[style_start:style_end].strip()
    colon = style_value.find(":")
    if colon < 0:
        return None
    style_expr = style_value[colon + 1 :].strip()
    if not style_expr.startswith("TextStyle("):
        return None
    paren_open = style_expr.index("(")
    paren_close = find_matching_paren(style_expr, paren_open)
    if paren_close is None:
        return None
    style_inner = style_expr[paren_open + 1 : paren_close].strip()
    extra = ", ".join(inner[start:end].strip() for _, start, end in misplaced)
    if style_inner:
        merged_style = f"style: TextStyle({style_inner}, {extra})"
    else:
        merged_style = f"style: TextStyle({extra})"
    rebuilt_parts: list[str] = []
    for name, start, end in args:
        if name in _TEXT_STYLE_ONLY_PARAMS:
            continue
        if name == "style":
            rebuilt_parts.append(merged_style)
        else:
            rebuilt_parts.append(inner[start:end].strip())
    return ", ".join(rebuilt_parts)


def _rebuild_text_call_inner(inner: str) -> str | None:
    args = list(_iter_top_level_call_args(inner))
    misplaced = [item for item in args if item[0] in _TEXT_STYLE_ONLY_PARAMS]
    if not misplaced:
        return None
    if any(item[0] == "style" for item in args):
        return _merge_misplaced_into_existing_style(inner, args, misplaced)
    style_parts = [inner[start:end].strip() for _, start, end in misplaced]
    kept = [inner[start:end].strip() for name, start, end in args if name not in _TEXT_STYLE_ONLY_PARAMS]
    if not kept:
        return f"style: TextStyle({', '.join(style_parts)})"
    rebuilt = kept[0]
    rebuilt = f"{rebuilt}, style: TextStyle({', '.join(style_parts)})"
    if len(kept) > 1:
        rebuilt = f"{rebuilt}, {', '.join(kept[1:])}"
    return rebuilt


def use_scale_down_for_design_canvas_fittedbox(source: str) -> str:
    """Never upscale the fixed Figma canvas on wide viewports (prevents stretched type)."""
    return _DESIGN_CANVAS_FITTED_CONTAIN_RE.sub(
        "FittedBox(\n                          fit: BoxFit.scaleDown,\n"
        "                          child: SizedBox(",
        source,
    )


def fix_elevated_button_label_on_saturated_background(source: str) -> str:
    """Use light label ink on saturated ``ElevatedButton`` fills (Figma often exports black)."""
    from figma_flutter_agent.generator.dart_delimiters import find_matching_paren

    parts: list[str] = []
    index = 0
    while True:
        match = _ELEVATED_BUTTON_OPENER_RE.search(source, index)
        if match is None:
            parts.append(source[index:])
            break
        parts.append(source[index : match.start()])
        paren_open = match.end() - 1
        paren_close = find_matching_paren(source, paren_open)
        if paren_close is None:
            parts.append(source[match.start() :])
            break
        block = source[match.start() : paren_close + 1]
        if (
            "backgroundColor:" in block
            and not _LIGHT_ELEVATED_BUTTON_BG_RE.search(block)
            and _TEXT_STYLE_BLACK_RE.search(block)
        ):
            block = block.replace(
                "color: Color(0xFF000000)",
                "color: Color(0xFFFFFFFF)",
            )
        parts.append(block)
        index = paren_close + 1
    return "".join(parts)


def wrap_misplaced_text_style_params_on_text(source: str) -> str:
    """Move top-level ``fontSize`` / ``fontWeight`` / … on ``Text`` into ``style: TextStyle``."""
    from figma_flutter_agent.generator.dart_delimiters import find_matching_paren

    parts: list[str] = []
    index = 0
    while True:
        match = _TEXT_OPENER_RE.search(source, index)
        if match is None:
            parts.append(source[index:])
            break
        parts.append(source[index : match.start()])
        const_prefix = match.group(1) or ""
        paren_open = match.end() - 1
        paren_close = find_matching_paren(source, paren_open)
        if paren_close is None:
            parts.append(source[match.start() :])
            break
        inner = source[paren_open + 1 : paren_close]
        rebuilt_inner = _rebuild_text_call_inner(inner)
        if rebuilt_inner is None:
            parts.append(source[match.start() : paren_close + 1])
        else:
            parts.append(f"{const_prefix}Text({rebuilt_inner})")
        index = paren_close + 1
    return "".join(parts)


def strip_garbage_closer_only_lines(source: str) -> str:
    """Drop lines like ``])))}}`` that dart format reports as ``Expected to find ';'``."""
    lines = source.splitlines()
    if not any(is_garbage_closer_only_line(line) for line in lines):
        return source
    return "\n".join(line for line in lines if not is_garbage_closer_only_line(line))


def parse_format_error_line_numbers(errors: tuple[str, ...] | list[str]) -> tuple[int, ...]:
    """Extract 1-based line numbers from ``dart format`` parser diagnostics."""
    numbers: list[int] = []
    for error in errors:
        match = _FORMAT_ERROR_LINE_RE.match(error.strip())
        if match is not None:
            numbers.append(int(match.group(1)))
    return tuple(dict.fromkeys(numbers))


def replace_image_network_calls(source: str) -> str:
    """Swap ``Image.network`` for a stable placeholder so golden tests can settle."""
    from figma_flutter_agent.generator.llm_dart import _find_matching_paren

    updated = source
    index = 0
    while True:
        start = updated.find("Image.network(", index)
        if start == -1:
            return updated
        paren_open = start + len("Image.network")
        paren_close = _find_matching_paren(updated, paren_open)
        if paren_close is None:
            return updated
        replacement = "const Icon(Icons.g_mobiledata, size: 24)"
        updated = updated[:start] + replacement + updated[paren_close + 1 :]
        index = start + len(replacement)


def apply_llm_dart_syntax_repairs(source: str) -> str:
    """Run deterministic repairs for common LLM Dart call-site mistakes."""
    updated = collapse_duplicate_child_named_params(source)
    updated = fix_misplaced_child_before_named_params(updated)
    updated = normalize_app_typography_style_references(updated)
    updated = wrap_misplaced_text_style_params_on_text(updated)
    updated = use_scale_down_for_design_canvas_fittedbox(updated)
    updated = fix_elevated_button_label_on_saturated_background(updated)
    updated = strip_duplicate_key_after_super(updated)
    updated = strip_orphan_semicolon_only_lines(updated)
    updated = strip_garbage_closer_only_lines(updated)
    return replace_image_network_calls(updated)
