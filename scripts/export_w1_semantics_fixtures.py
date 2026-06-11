"""Export W1 semantics corpus JSON fixtures from programmatic clean-tree builders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from figma_flutter_agent.schemas import CleanDesignTreeNode, WidgetIrKind
from tests.support.semantics_trees import (
    bordered_box_not_button_trap,
    compact_chip_row,
    container_card,
    filled_button,
    input_field,
    list_tile_row,
    outlined_button,
    plain_row_not_list_tile_trap,
    technical_divider,
    text_button,
    text_label_not_button_trap,
    thin_rect_not_divider_trap,
    weekday_chip_row,
)

POSITIVE = ROOT / "tests" / "fixtures" / "layouts" / "semantics" / "positive"
NEGATIVE = ROOT / "tests" / "fixtures" / "layouts" / "semantics" / "negative"


def _dump(path: Path, tree: CleanDesignTreeNode, **meta: object) -> None:
    payload = {
        "clean_tree": tree.model_dump(mode="json", by_alias=True),
        **meta,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
  positives: list[tuple[Path, CleanDesignTreeNode, str, WidgetIrKind]] = [
      (POSITIVE / "button_filled_primary.json", filled_button("btn-filled-1"), "btn-filled-1", WidgetIrKind.BUTTON_FILLED),
      (POSITIVE / "button_filled_secondary.json", filled_button("btn-filled-2", label="Submit"), "btn-filled-2", WidgetIrKind.BUTTON_FILLED),
      (POSITIVE / "button_filled_tertiary.json", filled_button("btn-filled-3", label="Save"), "btn-filled-3", WidgetIrKind.BUTTON_FILLED),
      (POSITIVE / "button_outlined_primary.json", outlined_button("btn-outlined-1"), "btn-outlined-1", WidgetIrKind.BUTTON_OUTLINED),
      (POSITIVE / "button_outlined_secondary.json", outlined_button("btn-outlined-2", label="Back"), "btn-outlined-2", WidgetIrKind.BUTTON_OUTLINED),
      (POSITIVE / "button_outlined_tertiary.json", outlined_button("btn-outlined-3", label="Edit"), "btn-outlined-3", WidgetIrKind.BUTTON_OUTLINED),
      (POSITIVE / "button_text_primary.json", text_button("btn-text-1"), "btn-text-1", WidgetIrKind.BUTTON_TEXT),
      (POSITIVE / "button_text_secondary.json", text_button("btn-text-2", label="Later"), "btn-text-2", WidgetIrKind.BUTTON_TEXT),
      (POSITIVE / "button_text_tertiary.json", text_button("btn-text-3", label="Dismiss"), "btn-text-3", WidgetIrKind.BUTTON_TEXT),
      (POSITIVE / "input_text_field_primary.json", input_field("input-1"), "input-1", WidgetIrKind.INPUT_TEXT_FIELD),
      (POSITIVE / "input_text_field_secondary.json", input_field("input-2"), "input-2", WidgetIrKind.INPUT_TEXT_FIELD),
      (POSITIVE / "input_text_field_tertiary.json", input_field("input-3"), "input-3", WidgetIrKind.INPUT_TEXT_FIELD),
      (POSITIVE / "chip_choice_weekday_row.json", weekday_chip_row("chip-row"), "chip-row", WidgetIrKind.CHIP_CHOICE),
      (POSITIVE / "chip_choice_numeric_row.json", compact_chip_row("chip-row-numeric"), "chip-row-numeric", WidgetIrKind.CHIP_CHOICE),
      (POSITIVE / "chip_choice_compact_row.json", compact_chip_row("chip-row-compact"), "chip-row-compact", WidgetIrKind.CHIP_CHOICE),
      (POSITIVE / "container_card_primary.json", container_card("card-1"), "card-1", WidgetIrKind.CONTAINER_CARD),
      (POSITIVE / "container_card_secondary.json", container_card("card-2"), "card-2", WidgetIrKind.CONTAINER_CARD),
      (POSITIVE / "container_card_tertiary.json", container_card("card-3"), "card-3", WidgetIrKind.CONTAINER_CARD),
      (POSITIVE / "container_list_tile_primary.json", list_tile_row("tile-1"), "tile-1", WidgetIrKind.CONTAINER_LIST_TILE),
      (POSITIVE / "container_list_tile_secondary.json", list_tile_row("tile-2"), "tile-2", WidgetIrKind.CONTAINER_LIST_TILE),
      (POSITIVE / "container_list_tile_tertiary.json", list_tile_row("tile-3"), "tile-3", WidgetIrKind.CONTAINER_LIST_TILE),
      (POSITIVE / "technical_divider_primary.json", technical_divider("divider-1"), "divider-1", WidgetIrKind.TECHNICAL_DIVIDER),
      (POSITIVE / "technical_divider_secondary.json", technical_divider("divider-2"), "divider-2", WidgetIrKind.TECHNICAL_DIVIDER),
      (POSITIVE / "technical_divider_tertiary.json", technical_divider("divider-3"), "divider-3", WidgetIrKind.TECHNICAL_DIVIDER),
  ]

  for path, tree, target_id, kind in positives:
      _dump(
          path,
          tree,
          target_figma_id=target_id,
          expected_kind=kind.value,
          forbidden_kinds=[],
      )

  w1_button_kinds = [
      WidgetIrKind.BUTTON_FILLED.value,
      WidgetIrKind.BUTTON_OUTLINED.value,
      WidgetIrKind.BUTTON_TEXT.value,
  ]
  _dump(
      NEGATIVE / "bordered_box_not_button.json",
      bordered_box_not_button_trap(),
      target_figma_id="border-trap",
      forbidden_kinds=w1_button_kinds,
  )
  _dump(
      NEGATIVE / "text_label_not_button.json",
      text_label_not_button_trap(),
      target_figma_id="label-trap",
      forbidden_kinds=w1_button_kinds,
  )
  _dump(
      NEGATIVE / "thin_rect_not_divider.json",
      thin_rect_not_divider_trap(),
      target_figma_id="thin-rect-trap",
      forbidden_kinds=[WidgetIrKind.TECHNICAL_DIVIDER.value],
  )
  _dump(
      NEGATIVE / "plain_row_not_list_tile.json",
      plain_row_not_list_tile_trap(),
      target_figma_id="row-trap",
      forbidden_kinds=[WidgetIrKind.CONTAINER_LIST_TILE.value],
  )


if __name__ == "__main__":
    main()
