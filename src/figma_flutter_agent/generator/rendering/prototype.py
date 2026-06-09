"""Prototype navigation rendering helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.navigation_codegen import PrototypeAction, has_scroll_actions


def render_scroll_targets(*, template: object) -> dict[str, str]:
    """Render scroll target registry used by SCROLL_TO prototype helpers."""
    return {"lib/core/prototype_scroll_targets.dart": template.render()}


def render_navigation(
    *,
    navigation_template: object,
    scroll_template: object,
    actions: list[PrototypeAction],
    routing_type: str,
) -> dict[str, str]:
    """Render prototype navigation helper methods for Figma reactions."""
    if not actions:
        return {}
    files = {
        "lib/core/prototype_navigation.dart": navigation_template.render(
            actions=actions,
            routing_type=routing_type,
            has_scroll_actions=has_scroll_actions(actions),
        )
    }
    if has_scroll_actions(actions):
        files.update(render_scroll_targets(template=scroll_template))
    return files
