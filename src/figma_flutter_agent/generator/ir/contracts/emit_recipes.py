"""Report-only Contract-to-Emit recipe registry.

The registry describes what future policy-gated emit should understand for each
recognized contract kind. It does not emit Dart and is not used by production emit.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from figma_flutter_agent.generator.ir.contracts.laws import (
    KNOWN_EFFECTS,
    LAYOUT_LAWS,
)

RolloutStage = Literal[
    "report_only",
    "diff_only",
    "policy_gated",
    "native_emit",
]

RiskLevel = Literal[
    "low",
    "medium",
    "high",
]

EmitStrategyKind = Literal[
    "native",
    "styled_primitive",
    "visual_fallback",
    "unsupported",
]


class ContractEmitRecipe(BaseModel):
    contract_kind: str
    role: str
    subtypes: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    preferred_native_emit: list[str] = Field(default_factory=list)
    styled_primitive_fallback: str | None = None
    visual_fallback: str | None = None

    required_owned_parts: list[str] = Field(default_factory=list)
    optional_owned_parts: list[str] = Field(default_factory=list)

    ownership_rules: list[str] = Field(default_factory=list)
    layout_laws: list[str] = Field(default_factory=list)
    accessibility_laws: list[str] = Field(default_factory=list)
    state_laws: list[str] = Field(default_factory=list)

    allowed_effects: list[str] = Field(default_factory=list)
    forbidden_effects: list[str] = Field(default_factory=list)

    risk_level: RiskLevel
    default_stage: RolloutStage

    emit_strategy_order: list[EmitStrategyKind] = Field(default_factory=list)

    notes: str | None = None


class ContractRecipeValidation(BaseModel):
    contract_kind: str
    subtype: str | None = None
    supported: bool
    missing_required_parts: list[str] = Field(default_factory=list)
    unknown_laws: list[str] = Field(default_factory=list)
    unknown_effects: list[str] = Field(default_factory=list)
    forbidden_effects_requested: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


CANONICAL_KIND_ALIASES: dict[str, str] = {
    "textarea": "multiline_text_input",
    "multiline": "multiline_text_input",
}

_DEFAULT_STRATEGY: list[EmitStrategyKind] = ["native", "styled_primitive", "visual_fallback"]
_UNSUPPORTED_STRATEGY: list[EmitStrategyKind] = ["unsupported", "visual_fallback"]
_REPORT_ONLY: RolloutStage = "report_only"


def _recipe(
    contract_kind: str,
    *,
    role: str,
    preferred_native_emit: list[str],
    styled_primitive_fallback: str,
    visual_fallback: str,
    required_owned_parts: list[str],
    optional_owned_parts: list[str],
    ownership_rules: list[str],
    layout_laws: list[str],
    accessibility_laws: list[str],
    state_laws: list[str],
    allowed_effects: list[str],
    forbidden_effects: list[str],
    risk_level: RiskLevel,
    subtypes: list[str] | None = None,
    aliases: list[str] | None = None,
    emit_strategy_order: list[EmitStrategyKind] | None = None,
    notes: str | None = None,
) -> ContractEmitRecipe:
    return ContractEmitRecipe(
        contract_kind=contract_kind,
        role=role,
        subtypes=subtypes or [],
        aliases=aliases or [],
        preferred_native_emit=preferred_native_emit,
        styled_primitive_fallback=styled_primitive_fallback,
        visual_fallback=visual_fallback,
        required_owned_parts=required_owned_parts,
        optional_owned_parts=optional_owned_parts,
        ownership_rules=ownership_rules,
        layout_laws=layout_laws,
        accessibility_laws=accessibility_laws,
        state_laws=state_laws,
        allowed_effects=allowed_effects,
        forbidden_effects=forbidden_effects,
        risk_level=risk_level,
        default_stage=_REPORT_ONLY,
        emit_strategy_order=emit_strategy_order or _DEFAULT_STRATEGY,
        notes=notes,
    )


_SINGLE_LINE_INPUT_LAWS = [
    "single_line_input_vertical_center",
    "input_metrics_over_bounds",
    "input_content_padding_single_source",
    "border_none_requires_bounded_height",
    "label_outside_control",
    "placeholder_as_hint",
    "value_as_field_content",
]
_SINGLE_LINE_INPUT_ALLOWED = [
    "lower_to_native_input",
    "attach_label",
    "attach_hint",
    "attach_value",
    "attach_prefix_icon",
    "attach_suffix_icon",
    "apply_vertical_center_law",
    "attach_text_field_accessibility",
]
_SINGLE_LINE_INPUT_FORBIDDEN = [
    "derive_password_from_text_only",
    "derive_keyboard_type_from_text_only",
    "treat_label_as_value",
    "emit_placeholder_as_sibling_text_after_lowering",
    "invent_geometry",
    "llm_generated_dart",
]


def _single_line_input_recipe(contract_kind: str) -> ContractEmitRecipe:
    allowed = list(_SINGLE_LINE_INPUT_ALLOWED)
    forbidden = list(_SINGLE_LINE_INPUT_FORBIDDEN)
    subtypes: list[str] = []
    if contract_kind == "password_input":
        allowed.extend(["obscure_text", "attach_visibility_toggle"])
        forbidden.extend(
            [
                "obscure_text_from_text_only",
                "expose_password_cleartext",
                "invent_visibility_toggle_icon",
            ]
        )
        subtypes.append("password")
    elif contract_kind == "search_input":
        allowed.extend(["attach_search_icon", "set_search_keyboard_intent"])
        forbidden.extend(["derive_search_from_text_only", "invent_search_icon"])
        subtypes.append("search")
    elif contract_kind in {"email_input", "phone_input"}:
        allowed.append("set_keyboard_intent")
        subtypes.append(contract_kind.removesuffix("_input"))

    return _recipe(
        contract_kind,
        role="text_input",
        subtypes=subtypes,
        preferred_native_emit=["TextField", "TextFormField"],
        styled_primitive_fallback="styled_input_shell",
        visual_fallback="preserve_visual_stack_or_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=[
            "label_node_ids",
            "hint_node_ids",
            "value_node_ids",
            "decoration_node_ids",
            "surface_node_id",
        ],
        ownership_rules=[
            "label_nodes_are_external_label_not_value",
            "hint_nodes_become_hint_text",
            "value_nodes_become_field_content",
            "decoration_nodes_become_prefix_or_suffix",
            "surface_node_owns_chrome",
        ],
        layout_laws=_SINGLE_LINE_INPUT_LAWS,
        accessibility_laws=[
            "a11y_role_text_field",
            "a11y_label_from_label_or_hint",
            "a11y_value_from_value_node",
        ],
        state_laws=[
            "disabled_from_variant_or_state",
            "error_from_contract_state",
            "required_from_contract_state",
        ],
        allowed_effects=allowed,
        forbidden_effects=forbidden,
        risk_level="high",
    )


TEXTAREA_RECIPE = _recipe(
    "multiline_text_input",
    role="text_input",
    subtypes=["textarea", "multiline"],
    aliases=["textarea", "multiline"],
    preferred_native_emit=["TextField", "TextFormField"],
    styled_primitive_fallback="styled_textarea_shell",
    visual_fallback="preserve_visual_stack_or_container",
    required_owned_parts=["control_node_id"],
    optional_owned_parts=[
        "label_node_ids",
        "hint_node_ids",
        "value_node_ids",
        "decoration_node_ids",
        "surface_node_id",
    ],
    ownership_rules=[
        "label_nodes_are_external_label_not_value",
        "hint_nodes_become_hint_text",
        "value_nodes_become_field_content",
        "surface_node_owns_chrome",
    ],
    layout_laws=[
        "multiline_input_top_align",
        "textarea_preserve_min_height",
        "placeholder_as_hint",
        "value_as_field_content",
        "label_outside_control",
        "input_content_padding_single_source",
    ],
    accessibility_laws=[
        "a11y_role_text_field",
        "a11y_multiline_text_field",
        "a11y_label_from_label_or_hint",
    ],
    state_laws=[
        "disabled_from_variant_or_state",
        "error_from_contract_state",
    ],
    allowed_effects=[
        "lower_to_multiline_text_field",
        "attach_label",
        "attach_hint",
        "attach_value",
        "apply_multiline_top_align_law",
        "attach_text_field_accessibility",
    ],
    forbidden_effects=[
        "center_multiline_text_vertically",
        "treat_label_as_value",
        "emit_placeholder_as_sibling_text_after_lowering",
        "invent_geometry",
        "llm_generated_dart",
    ],
    risk_level="high",
)


def _button_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="button",
        preferred_native_emit=[
            "FilledButton",
            "ElevatedButton",
            "OutlinedButton",
            "TextButton",
            "IconButton",
            "FloatingActionButton",
        ],
        styled_primitive_fallback="styled_button_shell",
        visual_fallback="preserve_visual_button_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=["label_node_ids", "decoration_node_ids", "surface_node_id"],
        ownership_rules=[
            "label_nodes_become_button_label",
            "decoration_nodes_become_button_icons",
            "surface_node_owns_button_chrome",
        ],
        layout_laws=[
            "button_label_centered",
            "button_content_padding_from_contract",
            "button_min_tap_target",
            "button_full_width_when_boundary_fills_parent",
        ],
        accessibility_laws=[
            "a11y_role_button",
            "a11y_label_from_label",
            "a11y_disabled_state",
        ],
        state_laws=[
            "disabled_from_variant_or_state",
            "loading_from_variant_or_state",
            "pressed_state_not_invented",
        ],
        allowed_effects=[
            "lower_to_native_button",
            "attach_button_label",
            "attach_button_icon",
            "attach_button_accessibility_role",
            "preserve_button_state",
        ],
        forbidden_effects=[
            "invent_on_pressed_behavior",
            "derive_action_kind_from_text_only",
            "invent_icon",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _chip_recipe(contract_kind: str) -> ContractEmitRecipe:
    is_group = contract_kind == "choice_chip_group"
    return _recipe(
        contract_kind,
        role="chip_group" if is_group else "chip",
        preferred_native_emit=["Wrap", "ChoiceChip", "FilterChip", "InputChip", "ActionChip"],
        styled_primitive_fallback="styled_chip_shell",
        visual_fallback="preserve_visual_chip_row_or_wrap",
        required_owned_parts=["control_node_id", "option_node_ids"]
        if is_group
        else ["control_node_id"],
        optional_owned_parts=["label_node_ids", "decoration_node_ids"],
        ownership_rules=[
            "option_nodes_become_chip_options",
            "label_nodes_become_group_label",
            "decoration_nodes_become_chip_icons",
            "selected_state_belongs_to_option",
        ],
        layout_laws=[
            "chip_options_preserve_visual_order",
            "chip_group_wrap_spacing_preserved",
            "chip_label_centered",
            "chip_selected_state_preserved",
            "chip_padding_from_contract",
        ],
        accessibility_laws=[
            "a11y_role_chip",
            "a11y_role_choice_group",
            "a11y_selected_state",
        ],
        state_laws=[
            "selected_from_variant_or_style",
            "disabled_from_variant_or_state",
            "not_selected_from_text",
        ],
        allowed_effects=[
            "lower_to_choice_chip_group",
            "lower_to_filter_chip_group",
            "attach_chip_options",
            "attach_selected_state",
            "attach_chip_accessibility",
        ],
        forbidden_effects=[
            "derive_selected_from_text_only",
            "invent_option",
            "invent_selection_state",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _rating_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="rating_input",
        preferred_native_emit=["rating_control", "Semantics+Row"],
        styled_primitive_fallback="styled_rating_row",
        visual_fallback="preserve_visual_star_row",
        required_owned_parts=["control_node_id", "option_node_ids"],
        optional_owned_parts=["label_node_ids"],
        ownership_rules=[
            "option_nodes_become_rating_units",
            "value_from_component_variant_or_filled_options",
            "label_nodes_become_rating_label",
        ],
        layout_laws=[
            "rating_value_from_component_variant_or_filled_options",
            "rating_options_preserve_order",
            "rating_gap_preserved",
            "rating_item_size_preserved",
            "rating_value_clamped_to_option_count",
        ],
        accessibility_laws=[
            "a11y_role_adjustable_or_value",
            "a11y_value_rating",
            "a11y_label_from_label",
        ],
        state_laws=[
            "rating_value_from_variant_or_option_state",
            "not_rating_value_from_text_only",
        ],
        allowed_effects=[
            "lower_to_rating_control",
            "attach_rating_value",
            "attach_rating_accessibility",
            "preserve_rating_option_order",
        ],
        forbidden_effects=[
            "derive_rating_value_from_nearby_text_only",
            "invent_rating_option",
            "invent_rating_value",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _selection_recipe(contract_kind: str) -> ContractEmitRecipe:
    is_group = contract_kind in {"radio_group", "segmented_control"}
    return _recipe(
        contract_kind,
        role="selection_control",
        preferred_native_emit=["Checkbox", "Switch", "Radio", "SegmentedButton"],
        styled_primitive_fallback="styled_selection_control",
        visual_fallback="preserve_visual_selection_row",
        required_owned_parts=["control_node_id", "option_node_ids"]
        if is_group
        else ["control_node_id"],
        optional_owned_parts=["label_node_ids", "decoration_node_ids"],
        ownership_rules=[
            "label_nodes_become_control_label",
            "option_nodes_become_selection_options",
            "selected_state_belongs_to_option_or_control",
        ],
        layout_laws=[
            "selection_control_label_center_aligned",
            "selection_tap_target_min_size",
            "selection_options_preserve_order",
            "selection_group_spacing_preserved",
        ],
        accessibility_laws=[
            "a11y_role_checkbox",
            "a11y_role_switch",
            "a11y_role_radio",
            "a11y_selected_or_checked_state",
            "a11y_label_from_label",
        ],
        state_laws=[
            "checked_from_variant_or_state",
            "selected_from_variant_or_state",
            "disabled_from_variant_or_state",
            "not_checked_from_text",
        ],
        allowed_effects=[
            "lower_to_native_checkbox",
            "lower_to_native_switch",
            "lower_to_native_radio",
            "lower_to_segmented_control",
            "attach_checked_state",
            "attach_selected_state",
            "attach_selection_accessibility",
        ],
        forbidden_effects=[
            "derive_checked_from_text_only",
            "derive_selected_from_text_only",
            "invent_group_value",
            "invent_on_changed_behavior",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _navigation_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="navigation",
        preferred_native_emit=[
            "AppBar",
            "NavigationBar",
            "BottomNavigationBar",
            "TabBar",
            "Drawer",
            "Stepper",
        ],
        styled_primitive_fallback="styled_navigation_shell",
        visual_fallback="preserve_visual_navigation_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=["label_node_ids", "option_node_ids", "decoration_node_ids"],
        ownership_rules=[
            "title_node_becomes_navigation_title",
            "option_nodes_become_navigation_items",
            "selected_state_belongs_to_navigation_item",
            "surface_node_owns_navigation_chrome",
        ],
        layout_laws=[
            "navigation_docked_position_preserved",
            "navigation_items_preserve_order",
            "navigation_selected_state_preserved",
            "app_bar_title_alignment",
            "bottom_bar_safe_area_respected",
        ],
        accessibility_laws=[
            "a11y_role_navigation",
            "a11y_selected_navigation_item",
            "a11y_label_from_item_label",
        ],
        state_laws=[
            "selected_index_from_variant_or_state",
            "disabled_from_variant_or_state",
        ],
        allowed_effects=[
            "lower_to_app_bar",
            "lower_to_navigation_bar",
            "lower_to_tab_bar",
            "attach_navigation_items",
            "attach_selected_index",
            "attach_navigation_accessibility",
        ],
        forbidden_effects=[
            "derive_selected_tab_from_text_only",
            "invent_navigation_destination",
            "invent_route_behavior",
            "hardcode_absolute_artboard_position_as_runtime_docking",
            "llm_generated_dart",
        ],
        risk_level="high",
    )


def _container_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="container",
        preferred_native_emit=["Card", "ListTile", "GridView", "PageView", "ExpansionTile"],
        styled_primitive_fallback="styled_container_shell",
        visual_fallback="preserve_visual_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=[
            "label_node_ids",
            "value_node_ids",
            "decoration_node_ids",
            "option_node_ids",
        ],
        ownership_rules=[
            "surface_node_owns_container_chrome",
            "title_node_becomes_title",
            "subtitle_node_becomes_subtitle",
            "media_node_becomes_leading_or_thumbnail",
            "action_node_becomes_trailing_action",
        ],
        layout_laws=[
            "container_padding_preserved",
            "list_tile_baseline_alignment",
            "grid_item_order_preserved",
            "carousel_item_order_preserved",
            "accordion_header_body_ownership",
        ],
        accessibility_laws=[
            "a11y_role_group_or_button_when_interactive",
            "a11y_label_from_title",
        ],
        state_laws=[
            "expanded_from_variant_or_state",
            "selected_from_variant_or_state",
        ],
        allowed_effects=[
            "lower_to_card",
            "lower_to_list_tile",
            "lower_to_grid",
            "lower_to_carousel",
            "lower_to_accordion",
            "attach_container_accessibility",
        ],
        forbidden_effects=[
            "invent_interactivity",
            "invent_list_tile_title",
            "invent_expanded_state",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _media_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="media",
        preferred_native_emit=["Image", "SvgPicture", "Icon", "CircleAvatar", "Badge"],
        styled_primitive_fallback="styled_media_shell",
        visual_fallback="preserve_visual_asset_or_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=["label_node_ids", "decoration_node_ids", "value_node_ids"],
        ownership_rules=[
            "asset_ref_becomes_media_source",
            "label_node_becomes_semantic_label",
            "badge_value_node_becomes_badge_label",
        ],
        layout_laws=[
            "media_bounds_preserved",
            "icon_size_preserved",
            "avatar_shape_preserved",
            "badge_position_preserved",
        ],
        accessibility_laws=[
            "a11y_image_label_when_meaningful",
            "a11y_exclude_decorative_media",
            "a11y_badge_value",
        ],
        state_laws=[
            "decorative_from_contract",
            "meaningful_from_contract",
        ],
        allowed_effects=[
            "lower_to_image",
            "lower_to_icon",
            "lower_to_avatar",
            "lower_to_badge",
            "attach_media_semantics",
        ],
        forbidden_effects=[
            "invent_asset_path",
            "invent_icon_from_name_only",
            "silent_missing_vector_fallback",
            "llm_generated_dart",
        ],
        risk_level="medium",
    )


def _feedback_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="feedback_overlay",
        preferred_native_emit=[
            "CircularProgressIndicator",
            "LinearProgressIndicator",
            "Tooltip",
            "Dialog",
            "BottomSheet",
            "SnackBar",
            "MaterialBanner",
        ],
        styled_primitive_fallback="styled_feedback_shell",
        visual_fallback="preserve_visual_feedback_container",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=[
            "label_node_ids",
            "value_node_ids",
            "decoration_node_ids",
            "option_node_ids",
        ],
        ownership_rules=[
            "message_node_becomes_feedback_message",
            "action_node_becomes_feedback_action",
            "surface_node_owns_feedback_chrome",
        ],
        layout_laws=[
            "overlay_surface_bounds_preserved",
            "feedback_message_order_preserved",
            "loader_size_preserved",
            "skeleton_shape_preserved",
        ],
        accessibility_laws=[
            "a11y_role_status_or_alert",
            "a11y_live_region_when_applicable",
            "a11y_label_from_message",
        ],
        state_laws=[
            "loading_from_contract",
            "error_from_contract_state",
        ],
        allowed_effects=[
            "lower_to_loader",
            "lower_to_tooltip",
            "lower_to_dialog",
            "lower_to_bottom_sheet",
            "lower_to_snackbar",
            "lower_to_banner",
            "attach_feedback_accessibility",
        ],
        forbidden_effects=[
            "invent_overlay_trigger",
            "invent_action_behavior",
            "invent_message",
            "llm_generated_dart",
        ],
        risk_level="high",
    )


def _technical_recipe(contract_kind: str) -> ContractEmitRecipe:
    return _recipe(
        contract_kind,
        role="technical_decorative",
        preferred_native_emit=["Divider", "SizedBox", "ExcludeSemantics"],
        styled_primitive_fallback="styled_technical_shell",
        visual_fallback="preserve_visual_node",
        required_owned_parts=["control_node_id"],
        optional_owned_parts=["decoration_node_ids"],
        ownership_rules=[
            "decorative_nodes_do_not_create_controls",
            "system_chrome_not_interactive_by_default",
            "spacer_preserves_space_not_semantics",
        ],
        layout_laws=[
            "divider_thickness_preserved",
            "spacer_size_preserved",
            "decorative_visual_preserved",
            "system_chrome_safe_area_respected",
        ],
        accessibility_laws=[
            "a11y_exclude_decorative",
            "a11y_system_chrome_excluded_or_labeled_by_policy",
        ],
        state_laws=[],
        allowed_effects=[
            "lower_to_divider",
            "lower_to_spacer",
            "exclude_decorative_semantics",
            "preserve_system_chrome_visual",
        ],
        forbidden_effects=[
            "invent_control_from_decorative",
            "derive_system_chrome_from_name_only",
            "invent_interactivity",
            "llm_generated_dart",
        ],
        risk_level="high" if contract_kind == "system_chrome" else "low",
    )


UNKNOWN_RECIPE = _recipe(
    "unknown",
    role="unknown",
    preferred_native_emit=[],
    styled_primitive_fallback="styled_technical_shell",
    visual_fallback="preserve_visual_node",
    required_owned_parts=["control_node_id"],
    optional_owned_parts=["decoration_node_ids"],
    ownership_rules=[
        "decorative_nodes_do_not_create_controls",
        "system_chrome_not_interactive_by_default",
        "spacer_preserves_space_not_semantics",
    ],
    layout_laws=[
        "decorative_visual_preserved",
    ],
    accessibility_laws=[
        "a11y_exclude_decorative",
    ],
    state_laws=[],
    allowed_effects=[
        "exclude_decorative_semantics",
    ],
    forbidden_effects=[
        "invent_control_from_decorative",
        "invent_interactivity",
        "llm_generated_dart",
    ],
    risk_level="high",
    emit_strategy_order=_UNSUPPORTED_STRATEGY,
    notes="Recognized fallback contract; native emit is intentionally not implemented.",
)

UNSUPPORTED_RECIPE = _recipe(
    "unsupported",
    role="unsupported",
    preferred_native_emit=[],
    styled_primitive_fallback="styled_technical_shell",
    visual_fallback="preserve_visual_node",
    required_owned_parts=[],
    optional_owned_parts=[],
    ownership_rules=[
        "unsupported_contracts_do_not_change_emit",
    ],
    layout_laws=[],
    accessibility_laws=[],
    state_laws=[],
    allowed_effects=[],
    forbidden_effects=[
        "llm_generated_dart",
        "invent_geometry",
        "invent_interactivity",
    ],
    risk_level="high",
    emit_strategy_order=_UNSUPPORTED_STRATEGY,
    notes="Unsupported contract kind; registry lookup returns this recipe instead of crashing.",
)


def _build_registry() -> dict[str, ContractEmitRecipe]:
    recipes: dict[str, ContractEmitRecipe] = {}
    for kind in [
        "text_input",
        "email_input",
        "phone_input",
        "search_input",
        "password_input",
    ]:
        recipes[kind] = _single_line_input_recipe(kind)
    recipes["multiline_text_input"] = TEXTAREA_RECIPE

    for kind in [
        "button",
        "primary_button",
        "outlined_button",
        "text_button",
        "icon_button",
        "fab_button",
    ]:
        recipes[kind] = _button_recipe(kind)

    for kind in [
        "choice_chip_group",
        "choice_chip",
        "filter_chip",
        "input_chip",
        "action_chip",
    ]:
        recipes[kind] = _chip_recipe(kind)

    for kind in ["rating_input", "star_rating"]:
        recipes[kind] = _rating_recipe(kind)

    for kind in ["checkbox", "switch", "radio", "radio_group", "segmented_control"]:
        recipes[kind] = _selection_recipe(kind)

    for kind in ["nav_bar", "app_bar", "bottom_bar", "tab_bar", "drawer", "pagination", "stepper"]:
        recipes[kind] = _navigation_recipe(kind)

    for kind in ["card", "list_tile", "grid", "carousel", "accordion"]:
        recipes[kind] = _container_recipe(kind)

    for kind in ["image", "icon", "avatar", "badge"]:
        recipes[kind] = _media_recipe(kind)

    for kind in ["loader", "skeleton", "tooltip", "dialog", "bottom_sheet", "snackbar", "banner"]:
        recipes[kind] = _feedback_recipe(kind)

    for kind in ["divider", "spacer", "decorative", "system_chrome"]:
        recipes[kind] = _technical_recipe(kind)

    recipes["unknown"] = UNKNOWN_RECIPE
    recipes["unsupported"] = UNSUPPORTED_RECIPE
    return recipes


_RECIPES_BY_KIND: dict[str, ContractEmitRecipe] = _build_registry()


def _canonical_kind(contract_kind: str | None) -> str:
    if not contract_kind:
        return "unsupported"
    return CANONICAL_KIND_ALIASES.get(contract_kind, contract_kind)


def get_contract_emit_recipe(
    contract_kind: str,
    subtype: str | None = None,
) -> ContractEmitRecipe:
    """Return a report-only recipe, falling back to explicit unsupported metadata."""
    canonical = _canonical_kind(contract_kind)
    recipe = _RECIPES_BY_KIND.get(canonical)
    if recipe is not None:
        return recipe
    if subtype:
        subtype_recipe = _RECIPES_BY_KIND.get(_canonical_kind(subtype))
        if subtype_recipe is not None:
            return subtype_recipe
    return UNSUPPORTED_RECIPE


def list_supported_contract_kinds() -> list[str]:
    """Return public supported contract kinds, excluding fallback recipes."""
    kinds = {kind for kind in _RECIPES_BY_KIND if kind not in {"unknown", "unsupported"}}
    kinds.update(CANONICAL_KIND_ALIASES)
    return sorted(kinds - {"unknown", "unsupported"})


def list_registered_contract_kinds() -> list[str]:
    """Return every addressable registry kind, including aliases and fallbacks."""
    return sorted(set(_RECIPES_BY_KIND) | set(CANONICAL_KIND_ALIASES))


def list_contract_emit_recipes() -> list[ContractEmitRecipe]:
    """Return unique canonical recipe objects in stable order."""
    return [_RECIPES_BY_KIND[kind] for kind in sorted(_RECIPES_BY_KIND)]


def expected_laws_for_contract(contract: Any) -> list[str]:
    """Return the report-only expected layout laws for a contract-like object."""
    contract_kind = _get_contract_field(contract, "contract_kind", "contractKind")
    subtype = _get_contract_field(contract, "subtype")
    recipe = get_contract_emit_recipe(str(contract_kind or ""), str(subtype) if subtype else None)
    return list(recipe.layout_laws)


def validate_contract_against_recipe(
    contract: Any,
    recipe: ContractEmitRecipe | None = None,
) -> ContractRecipeValidation:
    """Validate a contract-like object against the report-only recipe playbook."""
    raw_kind = _get_contract_field(contract, "contract_kind", "contractKind")
    subtype = _get_contract_field(contract, "subtype")
    contract_kind = str(raw_kind or "unsupported")
    resolved = recipe or get_contract_emit_recipe(contract_kind, str(subtype) if subtype else None)

    missing = [
        part
        for part in resolved.required_owned_parts
        if not _contract_has_owned_part(contract, part)
    ]
    contract_laws = _list_field(
        contract, "layout_laws", "proposed_layout_laws", "proposedLayoutLaws"
    )
    contract_effects = _list_field(
        contract,
        "allowed_effects",
        "proposed_effects",
        "proposedEffects",
    )
    unknown_laws = [law for law in contract_laws if law not in LAYOUT_LAWS]
    unknown_effects = [effect for effect in contract_effects if effect not in KNOWN_EFFECTS]
    forbidden = [effect for effect in contract_effects if effect in resolved.forbidden_effects]

    warnings: list[str] = []
    if resolved.contract_kind == "unsupported" and _canonical_kind(contract_kind) != "unsupported":
        warnings.append(f"Unsupported contract kind: {contract_kind}")

    return ContractRecipeValidation(
        contract_kind=resolved.contract_kind,
        subtype=str(subtype) if subtype else None,
        supported=resolved.contract_kind not in {"unknown", "unsupported"},
        missing_required_parts=missing,
        unknown_laws=unknown_laws,
        unknown_effects=unknown_effects,
        forbidden_effects_requested=forbidden,
        warnings=warnings,
    )


def _contract_has_owned_part(contract: Any, part: str) -> bool:
    if part == "hint_node_ids":
        values = _get_contract_field(
            contract, "hint_node_ids", "placeholder_node_ids", "placeholderNodeIds"
        )
    elif part == "surface_node_id":
        values = _get_contract_field(
            contract, "surface_node_id", "boundary_node_id", "boundaryNodeId"
        )
    else:
        values = _get_contract_field(contract, part, _snake_to_camel(part))
    if isinstance(values, list):
        return bool(values)
    return values is not None and values != ""


def _list_field(contract: Any, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        value = _get_contract_field(contract, name)
        if value is None:
            continue
        if isinstance(value, list):
            values.extend(str(item) for item in value)
            continue
        if isinstance(value, tuple | set):
            values.extend(str(item) for item in value)
            continue
        values.append(str(value))
    return values


def _get_contract_field(contract: Any, *names: str) -> Any:
    if isinstance(contract, dict):
        for name in names:
            if name in contract:
                return contract[name]
        return None
    for name in names:
        if hasattr(contract, name):
            return getattr(contract, name)
    if hasattr(contract, "model_dump"):
        dumped = contract.model_dump(by_alias=True)
        for name in names:
            if name in dumped:
                return dumped[name]
    return None


def _snake_to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)
