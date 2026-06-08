"""Text-related generated Dart repairs."""

from __future__ import annotations

import re

TEXT_DISPLAY_WIDGET_RE = re.compile(
    r"(?<!TextStyle)(?<!TextSpan)\b(?:Text(?:\.rich)?|SelectableText|EditableText|RichText)\s*\("
)


def fix_text_style_height_as_ratio(source: str) -> str:
    """Rewrite pixel-like ``TextStyle.height`` values to unitless line-height ratios."""
    from figma_flutter_agent.parser.numeric_rounding import format_micro_style_literal
    from figma_flutter_agent.parser.text_line_height import flutter_text_style_height_ratio

    parts: list[str] = []
    last = 0
    for match in re.finditer(r"\bheight:\s*([\d.]+)", source):
        parts.append(source[last : match.start()])
        height_val = float(match.group(1))
        window = source[max(0, match.start() - 600) : match.start()]
        font_matches = list(re.finditer(r"fontSize:\s*([\d.]+)", window))
        if not font_matches:
            parts.append(match.group(0))
        else:
            font_size = float(font_matches[-1].group(1))
            ratio = flutter_text_style_height_ratio(height_val, font_size=font_size)
            if ratio is None or ratio == height_val:
                parts.append(match.group(0))
            else:
                parts.append(f"height: {format_micro_style_literal(ratio)}")
        last = match.end()
    parts.append(source[last:])
    return "".join(parts)


def fix_empty_text_before_text_scaler(source: str) -> str:
    return re.sub(
        r"\bText\s*\(\s*,\s*textScaler:",
        "Text('', textScaler:",
        source,
    )


def ensure_text_style_leading_distribution(source: str) -> str:
    return re.sub(
        r"(TextStyle\([^)]*height:\s*[^,)]+)",
        r"\1, leadingDistribution: TextLeadingDistribution.proportional",
        source,
        count=1,
    )


def fix_misplaced_text_style_parameters(source: str) -> str:
    return source
