"""Predicate overlap matrix for flex dispatch audit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_row_label_value_summary_row,
    layout_fact_row_numeric_counter_badge,
    layout_fact_row_space_between_text_metric_row,
    layout_fact_row_status_pill_badge,
    layout_fact_row_tight_horizontal_pill_label,
    layout_fact_row_tight_overflow_guard_label_row,
)
from figma_flutter_agent.parser.interaction import (
    layout_fact_checkbox_control,
    layout_fact_hosts_compact_checkbox_control,
    layout_fact_textarea_field,
    row_hosts_checkbox_label_pair,
)
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
)


@dataclass(frozen=True, slots=True)
class PatternFixture:
    """Synthetic clean-tree pattern for matrix rows."""

    pattern_id: str
    node: CleanDesignTreeNode
    winning_emit: str


@dataclass(frozen=True, slots=True)
class PredicateSpec:
    """Named predicate evaluated on a pattern node."""

    name: str
    fn: Callable[[CleanDesignTreeNode], bool]


PREDICATE_SPECS: tuple[PredicateSpec, ...] = (
    PredicateSpec(
        "layout_fact_row_label_value_summary_row", layout_fact_row_label_value_summary_row
    ),
    PredicateSpec(
        "layout_fact_row_space_between_text_metric_row",
        layout_fact_row_space_between_text_metric_row,
    ),
    PredicateSpec(
        "layout_fact_row_tight_horizontal_pill_label", layout_fact_row_tight_horizontal_pill_label
    ),
    PredicateSpec(
        "layout_fact_row_tight_overflow_guard_label_row",
        layout_fact_row_tight_overflow_guard_label_row,
    ),
    PredicateSpec("layout_fact_row_status_pill_badge", layout_fact_row_status_pill_badge),
    PredicateSpec("layout_fact_row_numeric_counter_badge", layout_fact_row_numeric_counter_badge),
    PredicateSpec("row_hosts_checkbox_label_pair", row_hosts_checkbox_label_pair),
    PredicateSpec(
        "layout_fact_hosts_compact_checkbox_control", layout_fact_hosts_compact_checkbox_control
    ),
    PredicateSpec("layout_fact_checkbox_control", layout_fact_checkbox_control),
    PredicateSpec("layout_fact_textarea_field", layout_fact_textarea_field),
)


def _absolute_summary_row() -> CleanDesignTreeNode:
    label_stack = CleanDesignTreeNode(
        id="1:label-stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=50.5, height=21.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Items",
                type=NodeType.TEXT,
                text="Items",
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(left=-0.1, top=-1.0, width=50.8, height=21.0),
            )
        ],
    )
    value_stack = CleanDesignTreeNode(
        id="1:value-stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=44.3, height=21.0),
        children=[
            CleanDesignTreeNode(
                id="1:value",
                name="Total",
                type=NodeType.TEXT,
                text="1194",
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(left=0.0, top=-1.0, width=44.7, height=21.0),
            )
        ],
    )
    return CleanDesignTreeNode(
        id="1:row",
        name="SummaryRow",
        type=NodeType.ROW,
        alignment=Alignment(main="spaceBetween", cross="center"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=350.0, height=29.0),
        children=[label_stack, value_stack],
    )


def _plain_summary_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="2:row",
        name="Background",
        type=NodeType.ROW,
        alignment=Alignment(main="spaceBetween", cross="center"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=57.5),
        children=[
            CleanDesignTreeNode(
                id="2:left",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=61.6, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="2:label",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Subtotal",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="2:right",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=58.7, height=25.5),
                children=[
                    CleanDesignTreeNode(
                        id="2:value",
                        name="Value",
                        type=NodeType.TEXT,
                        text="1088",
                    )
                ],
            ),
        ],
    )


def _painted_pill_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="3:pill",
        name="Chip",
        type=NodeType.ROW,
        sizing=Sizing(width=64.0, height=23.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="3:label",
                name="Label",
                type=NodeType.TEXT,
                text="-20%",
                style=NodeStyle(font_size=12.0),
            )
        ],
    )


def _unpainted_tight_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="4:chip",
        name="ChipRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=64.0, height=17.0),
        children=[
            CleanDesignTreeNode(
                id="4:label",
                name="Label",
                type=NodeType.TEXT,
                text="Support",
                style=NodeStyle(font_size=12.0),
            )
        ],
    )


def _consent_checkbox_row() -> CleanDesignTreeNode:
    checkbox = CleanDesignTreeNode(
        id="5:cb",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=13.0, height=13.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFF767676",
            border_width=1.0,
            border_radius=2.5,
        ),
    )
    return CleanDesignTreeNode(
        id="5:row",
        name="Label",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=80.0),
        spacing=12.0,
        children=[
            CleanDesignTreeNode(
                id="5:margin",
                name="Input:margin",
                type=NodeType.COLUMN,
                sizing=Sizing(width=13.0, height=24.0),
                children=[checkbox],
            ),
            CleanDesignTreeNode(
                id="5:wrap",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=254.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="5:text",
                        name="Consent",
                        type=NodeType.TEXT,
                        text="Use card by default for online payments.",
                    )
                ],
            ),
        ],
    )


def _prefilled_input() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="6:input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        padding=Padding(top=17.5, bottom=17.5, left=16.0, right=16.0),
        children=[
            CleanDesignTreeNode(
                id="6:value",
                name="Value",
                type=NodeType.TEXT,
                text="New card",
                style=NodeStyle(font_size=14.0, line_height=1.2),
            )
        ],
    )


PATTERN_FIXTURES: tuple[PatternFixture, ...] = (
    PatternFixture(
        "spaceBetween_absolute_stacks",
        _absolute_summary_row(),
        "generic Row + SizedBox+Stack (overflow guard)",
    ),
    PatternFixture(
        "spaceBetween_plain_stacks",
        _plain_summary_row(),
        "try_render_space_between_text_metric_row flatten",
    ),
    PatternFixture(
        "painted_pill_23px",
        _painted_pill_row(),
        "layout_fact_row_tight_horizontal_pill_label + FittedBox",
    ),
    PatternFixture(
        "unpainted_tight_row_64x17",
        _unpainted_tight_row(),
        "layout_fact_row_tight_overflow_guard_label_row + Expanded ellipsis",
    ),
    PatternFixture(
        "consent_checkbox_row",
        _consent_checkbox_row(),
        "_try_render_checkbox_label_row",
    ),
    PatternFixture(
        "prefilled_flex_input",
        _prefilled_input(),
        "_render_stack_input / flex INPUT",
    ),
)


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One predicate × pattern evaluation."""

    pattern_id: str
    predicate: str
    matches: bool
    winning_emit: str


def build_predicate_matrix() -> list[MatrixCell]:
    """Evaluate all predicates against synthetic pattern fixtures."""
    cells: list[MatrixCell] = []
    for pattern in PATTERN_FIXTURES:
        for spec in PREDICATE_SPECS:
            cells.append(
                MatrixCell(
                    pattern_id=pattern.pattern_id,
                    predicate=spec.name,
                    matches=bool(spec.fn(pattern.node)),
                    winning_emit=pattern.winning_emit,
                )
            )
    return cells


def render_matrix_markdown(cells: list[MatrixCell]) -> str:
    """Render predicate matrix as a markdown table."""
    patterns = [item.pattern_id for item in PATTERN_FIXTURES]
    predicates = [item.name for item in PREDICATE_SPECS]
    lines = [
        "# Predicate overlap matrix",
        "",
        "Synthetic pattern fixtures × flex/interaction predicates. "
        "Multiple matches on one row signal archetype overlap risk.",
        "",
        "| Predicate | " + " | ".join(patterns) + " |",
        "| --- | " + " | ".join(["---"] * len(patterns)) + " |",
    ]
    for predicate in predicates:
        row_cells = []
        for pattern_id in patterns:
            match = next(
                (
                    cell.matches
                    for cell in cells
                    if cell.predicate == predicate and cell.pattern_id == pattern_id
                ),
                False,
            )
            row_cells.append("yes" if match else "no")
        lines.append(f"| `{predicate}` | " + " | ".join(row_cells) + " |")
    lines.extend(["", "## Winning emit per pattern", ""])
    for pattern in PATTERN_FIXTURES:
        matches = [
            cell.predicate
            for cell in cells
            if cell.pattern_id == pattern.pattern_id and cell.matches
        ]
        lines.append(f"- **{pattern.pattern_id}**: `{pattern.winning_emit}`")
        if matches:
            lines.append(f"  - predicates: {', '.join(f'`{name}`' for name in matches)}")
    overlap_rows = []
    for pattern_id in patterns:
        matched = [
            cell.predicate for cell in cells if cell.pattern_id == pattern_id and cell.matches
        ]
        if len(matched) > 3:
            overlap_rows.append((pattern_id, len(matched), matched))
    if overlap_rows:
        lines.extend(["", "## High overlap patterns", ""])
        for pattern_id, count, matched in sorted(overlap_rows, key=lambda item: -item[1]):
            lines.append(f"- `{pattern_id}`: {count} predicates — {', '.join(matched)}")
    return "\n".join(lines) + "\n"
