"""Multiline copy, RichText, and text patching utilities."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DART_STRING_LITERAL_RE = re.compile(
    r"""(['"])(?P<body>(?:\\.|(?!\1).)*)\1""",
    re.DOTALL,
)

_COPY_WIDTH_METRIC_SLACK = 1.06
_PROPORTIONAL_LEADING_MIN_LINE_HEIGHT = 1.15
_LINE_HEIGHT_RATIO_UPPER_BOUND = 3.0


def _copy_layout_width_for_metrics(figma_width: float) -> float:
    """Add slack so Flutter font metrics do not clip Figma-sized copy blocks."""
    slack_width = figma_width * _COPY_WIDTH_METRIC_SLACK
    return (
        round(slack_width, 1)
        if slack_width != int(slack_width)
        else float(int(slack_width))
    )


def _dart_single_quoted_literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{escaped}'"


def _first_dart_string_body(source: str) -> str | None:
    """Return decoded content of the first Dart string literal in ``source``."""
    match = _DART_STRING_LITERAL_RE.search(source)
    if match is None:
        return None
    return match.group("body")


def _iter_dart_string_literals(source: str):
    """Yield ``(start, end, body)`` for each Dart string literal in ``source``."""
    for match in _DART_STRING_LITERAL_RE.finditer(source):
        yield match.start(), match.end(), match.group("body")


def sanitize_figma_display_text(text: str) -> str:
    """Normalize Figma copy for Flutter Text widgets."""
    updated = text.replace("\r\n", "\n")
    updated = re.sub(r"[ \t]+\n", "\n", updated)
    updated = re.sub(r"\n[ \t]+", "\n", updated)
    updated = updated.rstrip()
    if updated.endswith("\n"):
        updated = updated.rstrip("\n").rstrip()
    return updated


def _decode_dart_string_literal_content(text: str) -> str:
    """Decode escape sequences from a Dart single-quoted string body."""
    decoded: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\" or index + 1 >= len(text):
            decoded.append(char)
            index += 1
            continue
        escape = text[index + 1]
        if escape == "n":
            decoded.append("\n")
        elif escape == "r":
            decoded.append("\r")
        elif escape == "t":
            decoded.append("\t")
        elif escape == "\\":
            decoded.append("\\")
        elif escape == "'":
            decoded.append("'")
        elif escape == '"':
            decoded.append('"')
        else:
            decoded.append(escape)
        index += 2
    return "".join(decoded)


def _normalize_text_for_match(text: str, *, from_dart_literal: bool = False) -> str:
    if from_dart_literal:
        text = _decode_dart_string_literal_content(text)
    return " ".join(sanitize_figma_display_text(text).split())


def _figma_literal(text: str) -> str:
    return _dart_single_quoted_literal(sanitize_figma_display_text(text))


def _extract_widget_style_expr(widget_block: str) -> str | None:
    """Return the full `style:` expression from a Text/RichText widget block."""
    marker = re.search(r"\bstyle:\s*", widget_block)
    if marker is None:
        return None
    index = marker.end()
    while index < len(widget_block) and widget_block[index].isspace():
        index += 1
    if index >= len(widget_block):
        return None
    if widget_block[index] in {"'", '"'}:
        quote = widget_block[index]
        index += 1
        escape = False
        while index < len(widget_block):
            char = widget_block[index]
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                index += 1
                break
            index += 1
    else:
        depth = 0
        while index < len(widget_block):
            char = widget_block[index]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char == "," and depth == 0:
                break
            index += 1
    return widget_block[marker.end() : index].strip()


def _multiline_copy_line_widget(
    *,
    line_literal: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    return (
        "FittedBox(\n"
        "                                      fit: BoxFit.scaleDown,\n"
        f"                                      child: Text({line_literal}, "
        f"{align_prefix}"
        "softWrap: false, "
        f"style: {style_expr}, "
        "textScaler: MediaQuery.textScalerOf(context)),\n"
        "                                    )"
    )


def _multiline_copy_text_widget(
    *,
    sanitized_text: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    """Render Figma hard line breaks as one Text per line (no soft-wrap reflow)."""
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        literal = _figma_literal(sanitized_text)
        return (
            f"Text({literal}, "
            f"{align_prefix}"
            "softWrap: false, "
            f"style: {style_expr}, "
            "textScaler: MediaQuery.textScalerOf(context))"
        )
    return (
        "Column(\n"
        "                                  mainAxisSize: MainAxisSize.min,\n"
        "                                  children: [\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(first_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(second_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        "                                  ],\n"
        "                                )"
    )


def _target_text_positioned_height(node: CleanDesignTreeNode) -> float | None:
    """Return a minimum Positioned height when Figma box would clip glyph metrics."""
    if node.type != NodeType.TEXT or node.stack_placement is None:
        return None
    placement_height = node.stack_placement.height
    if placement_height is None:
        return None
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return None
    line_factor = node.style.line_height if node.style.line_height else 1.2
    min_height = font_size * line_factor
    if node.style.glyph_height is not None:
        min_height = max(min_height, node.style.glyph_height + 2.0)
    if placement_height >= min_height * 0.95:
        return None
    return round(min_height + 2.0, 1)


def _figma_multiline_text_frame(node: CleanDesignTreeNode) -> bool:
    """True when the Figma text box is taller than a single line (wrap in Flutter)."""
    if node.type != NodeType.TEXT:
        return False
    if "\n" in (node.text or ""):
        return True
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return False
    line_factor = node.style.line_height if node.style.line_height else 1.2
    placement = node.stack_placement
    if placement is None or placement.height is None:
        return False
    single_line_height = font_size * line_factor
    return float(placement.height) >= single_line_height * 1.35


def _estimated_text_width(node: CleanDesignTreeNode) -> float | None:
    text = (node.text or "").strip()
    font_size = node.style.font_size
    if not text or font_size is None or font_size <= 0:
        return None
    weight = (node.style.font_weight or "").lower()
    weight_scale = 1.12 if weight in {"w700", "w800", "w900", "bold"} else 1.0
    if weight in {"w500", "w600", "medium", "semibold"}:
        weight_scale = 1.05
    per_char = font_size * 0.56 * weight_scale
    letter_spacing = node.style.letter_spacing or 0.0
    width = len(text) * per_char + max(0, len(text) - 1) * letter_spacing
    return round(width + 12.0, 1)


def strip_tight_proportional_leading_in_text_styles(content: str) -> str:
    """Remove proportional leading when ``TextStyle.height`` is below a safe ratio.

    Flutter Web can paint zero-height glyphs when ``TextLeadingDistribution.proportional``
    is paired with a tight line-height factor inside a fixed ``Positioned`` box.
    """
    updated = content
    search_from = 0
    while True:
        match = re.search(r"height:\s*([\d.]+)", updated[search_from:])
        if match is None:
            break
        abs_start = search_from + match.start()
        try:
            ratio = float(match.group(1))
        except ValueError:
            search_from = abs_start + 1
            continue
        if ratio >= _PROPORTIONAL_LEADING_MIN_LINE_HEIGHT or ratio < 0.5:
            search_from = abs_start + match.end() - match.start()
            continue
        if ratio > _LINE_HEIGHT_RATIO_UPPER_BOUND:
            search_from = abs_start + match.end() - match.start()
            continue
        tail_start = search_from + match.end()
        trailing = updated[tail_start : tail_start + 220]
        leading = re.match(
            r"\s*,\s*leadingDistribution:\s*TextLeadingDistribution\.proportional,?",
            trailing,
            re.DOTALL,
        )
        if leading is None:
            search_from = tail_start
            continue
        updated = updated[:tail_start] + updated[tail_start + leading.end() :]
        search_from = abs_start
    return updated


