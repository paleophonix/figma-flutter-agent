"""Report-only Contract-to-Emit recipe registry tests."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.contracts import (
    ContractEmitRecipe,
    get_contract_emit_recipe,
    list_contract_emit_recipes,
    list_registered_contract_kinds,
    list_supported_contract_kinds,
    validate_contract_against_recipe,
)


def test_contract_emit_registry_lists_supported_kinds() -> None:
    kinds = set(list_supported_contract_kinds())
    assert {
        "text_input",
        "textarea",
        "multiline_text_input",
        "button",
        "choice_chip_group",
        "rating_input",
        "checkbox",
        "switch",
        "radio",
        "nav_bar",
        "card",
        "image",
        "dialog",
        "divider",
        "decorative",
        "system_chrome",
    } <= kinds
    assert "unknown" not in kinds
    assert "unsupported" not in kinds


def test_contract_emit_registry_has_unknown_and_unsupported_recipes() -> None:
    registered = set(list_registered_contract_kinds())
    assert get_contract_emit_recipe("unknown").contract_kind == "unknown"
    assert get_contract_emit_recipe("unsupported").contract_kind == "unsupported"
    assert {"unknown", "unsupported"} <= registered


def test_textarea_aliases_resolve_to_same_recipe() -> None:
    textarea = get_contract_emit_recipe("textarea")
    multiline = get_contract_emit_recipe("multiline_text_input")
    assert textarea is multiline
    assert textarea.contract_kind == "multiline_text_input"


def test_text_input_recipe_contains_vertical_center_law() -> None:
    recipe = get_contract_emit_recipe("text_input")
    assert "single_line_input_vertical_center" in recipe.layout_laws
    assert {"TextField", "TextFormField"} & set(recipe.preferred_native_emit)
    assert "derive_password_from_text_only" in recipe.forbidden_effects


def test_textarea_recipe_contains_top_align_law() -> None:
    recipe = get_contract_emit_recipe("textarea")
    assert "multiline_input_top_align" in recipe.layout_laws
    assert "center_multiline_text_vertically" in recipe.forbidden_effects


def test_button_recipe_contains_native_button_candidates() -> None:
    recipe = get_contract_emit_recipe("button")
    assert {
        "FilledButton",
        "OutlinedButton",
        "TextButton",
        "IconButton",
    } & set(recipe.preferred_native_emit)


def test_chip_group_recipe_preserves_selected_state_law() -> None:
    recipe = get_contract_emit_recipe("choice_chip_group")
    assert "chip_selected_state_preserved" in recipe.layout_laws
    assert "selected_from_variant_or_style" in recipe.state_laws
    assert "derive_selected_from_text_only" in recipe.forbidden_effects


def test_rating_recipe_value_not_from_text_only() -> None:
    recipe = get_contract_emit_recipe("rating_input")
    assert "rating_value_from_component_variant_or_filled_options" in recipe.layout_laws
    assert "derive_rating_value_from_nearby_text_only" in recipe.forbidden_effects


def test_selection_recipes_have_checked_or_selected_state_laws() -> None:
    for kind in ["checkbox", "switch", "radio"]:
        recipe = get_contract_emit_recipe(kind)
        assert {
            "checked_from_variant_or_state",
            "selected_from_variant_or_state",
        } & set(recipe.state_laws)
        assert {
            "derive_checked_from_text_only",
            "derive_selected_from_text_only",
        } <= set(recipe.forbidden_effects)


def test_navigation_recipe_forbids_absolute_runtime_docking() -> None:
    recipe = get_contract_emit_recipe("nav_bar")
    assert "hardcode_absolute_artboard_position_as_runtime_docking" in recipe.forbidden_effects


def test_unknown_contract_kind_returns_unsupported_recipe() -> None:
    assert get_contract_emit_recipe("does_not_exist").contract_kind == "unsupported"


def test_validate_contract_reports_missing_required_parts() -> None:
    validation = validate_contract_against_recipe(
        {
            "contract_kind": "choice_chip_group",
            "control_node_id": "1:1",
            "option_node_ids": [],
        }
    )
    assert "option_node_ids" in validation.missing_required_parts


def test_validate_contract_rejects_forbidden_effect() -> None:
    validation = validate_contract_against_recipe(
        {
            "contract_kind": "text_input",
            "control_node_id": "1:1",
            "proposed_effects": ["derive_password_from_text_only"],
        }
    )
    assert "derive_password_from_text_only" in validation.forbidden_effects_requested


def test_validate_contract_reports_unknown_law() -> None:
    validation = validate_contract_against_recipe(
        {
            "contract_kind": "text_input",
            "control_node_id": "1:1",
            "proposed_layout_laws": ["magic_unknown_law"],
        }
    )
    assert "magic_unknown_law" in validation.unknown_laws


def test_validate_contract_reports_unknown_effect() -> None:
    validation = validate_contract_against_recipe(
        {
            "contract_kind": "text_input",
            "control_node_id": "1:1",
            "proposed_effects": ["magic_unknown_effect"],
        }
    )
    assert "magic_unknown_effect" in validation.unknown_effects


def test_recipes_are_report_only() -> None:
    for recipe in list_contract_emit_recipes():
        assert isinstance(recipe, ContractEmitRecipe)
        assert recipe.default_stage == "report_only"
        dumped = recipe.model_dump()
        assert "emit" not in dumped
        assert all("```dart" not in str(value).lower() for value in dumped.values())
        assert all("Widget build(" not in str(value) for value in dumped.values())
        assert not any(callable(value) for value in dumped.values())
