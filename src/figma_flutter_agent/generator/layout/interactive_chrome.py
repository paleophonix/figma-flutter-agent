"""Interactive control helper injection for generated widget files."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.choice_chip_row import (
    circular_option_chip_row_stateful_helpers,
)
from figma_flutter_agent.generator.layout.interactive_time import (
    time_wheel_picker_stateful_helpers,
)
from figma_flutter_agent.generator.layout.interactive_toggle import (
    toggle_checkbox_stateful_helpers,
)
from figma_flutter_agent.generator.layout.interactive_weekday import (
    weekday_chip_row_stateful_helpers,
)

_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+(?!_WheelPickerColumnSpec)(?!_GeneratedTimeWheelPicker)"
    r"(?!_GeneratedWeekdayChipRow)(?!_GeneratedCircularOptionChipRow)"
    r"(?!_GeneratedToggleCheckbox)(\w+)\s+extends\s+(?:Stateless|Stateful)Widget\b"
)

_HELPER_SPECS: tuple[tuple[str, str, object, str], ...] = (
    (
        "_GeneratedTimeWheelPicker(",
        "class _GeneratedTimeWheelPicker extends StatefulWidget",
        time_wheel_picker_stateful_helpers,
        "widget-time-wheel",
    ),
    (
        "_GeneratedWeekdayChipRow(",
        "class _GeneratedWeekdayChipRow extends StatefulWidget",
        weekday_chip_row_stateful_helpers,
        "widget-weekday-row",
    ),
    (
        "_GeneratedCircularOptionChipRow(",
        "class _GeneratedCircularOptionChipRow extends StatefulWidget",
        circular_option_chip_row_stateful_helpers,
        "widget-circular-chip-row",
    ),
)


def ensure_interactive_layout_helpers(source: str) -> str:
    """Inject private interactive helpers into widget files that reference them."""
    helpers_blocks: list[str] = []
    for use_marker, class_marker, factory, node_id in _HELPER_SPECS:
        if use_marker in source and class_marker not in source:
            helpers_blocks.append(factory(node_id))
    if (
        "_GeneratedToggleCheckbox(" in source
        and "class _GeneratedToggleCheckbox extends StatefulWidget" not in source
    ):
        helpers_blocks.append(toggle_checkbox_stateful_helpers())
    if not helpers_blocks:
        return source
    decl = _WIDGET_CLASS_DECL_RE.search(source)
    if decl is None:
        return source
    combined = "\n".join(helpers_blocks)
    source = f"{source[: decl.start()]}{combined}\n{source[decl.start() :]}"
    if "CupertinoPicker" in source and "package:flutter/cupertino.dart" not in source:
        material_import = re.search(r"import 'package:flutter/material.dart';\n", source)
        if material_import is not None:
            cupertino = "import 'package:flutter/cupertino.dart';\n"
            insert_at = material_import.end()
            source = f"{source[:insert_at]}{cupertino}{source[insert_at:]}"
    return source
