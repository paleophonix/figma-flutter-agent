"""Apply scoped LLM repair patches onto a generation payload."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    ExtractedWidget,
    FlutterGenerationResponse,
    FlutterRepairPatchResponse,
)


def apply_repair_patches(
    current: FlutterGenerationResponse,
    patch_response: FlutterRepairPatchResponse,
) -> FlutterGenerationResponse:
    """Merge repair patches into an existing generation payload.

    Args:
        current: Generation state before repair.
        patch_response: Scoped patches emitted by the repair LLM call.

    Returns:
        Updated generation payload with patched targets only.

    Raises:
        ValueError: When a widget patch omits ``widgetName`` or names an unknown target.
    """
    if not patch_response.patches:
        return current

    screen_code = current.screen_code
    widgets = list(current.extracted_widgets)
    widget_index = {widget.widget_name: index for index, widget in enumerate(widgets)}

    for patch in patch_response.patches:
        if patch.target == "screenCode":
            screen_code = patch.code
            continue
        if patch.target != "extractedWidget":
            msg = f"Unsupported repair patch target: {patch.target!r}"
            raise ValueError(msg)
        if not patch.widget_name:
            msg = "extractedWidget repair patches must include widgetName."
            raise ValueError(msg)
        updated = ExtractedWidget(widget_name=patch.widget_name, code=patch.code)
        if patch.widget_name in widget_index:
            widgets[widget_index[patch.widget_name]] = updated
        else:
            widget_index[patch.widget_name] = len(widgets)
            widgets.append(updated)

    return FlutterGenerationResponse(
        screen_code=screen_code,
        extracted_widgets=widgets,
    )
