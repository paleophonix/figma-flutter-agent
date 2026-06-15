"""Button and label color fix utilities."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_paren as _find_matching_paren,
)
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .positioned import _collect_all_nodes, _first_text_descendant


def _label_color_expr_for_filled_control(
    background_node: CleanDesignTreeNode,
    label_node: CleanDesignTreeNode,
) -> str:
    """Label color from Figma text fill; fall back to onPrimary only when the tree has no fill."""
    del background_node
    return dart_color_expr(
        label_node.style,
        css_key="color",
        fallback="Theme.of(context).colorScheme.onPrimary",
    )


def _collect_button_style_specs(
    clean_tree: CleanDesignTreeNode,
) -> dict[str, tuple[str, str]]:
    """Map button label copy to (background Color expr, label Color expr) from the clean tree."""
    specs: dict[str, tuple[str, str]] = {}
    for node in _collect_all_nodes(clean_tree):
        if node.type == NodeType.BUTTON:
            label_node = _first_text_descendant(node)
            if label_node is None or not label_node.text:
                continue
            background_expr = dart_color_expr(
                node.style,
                css_key="background-color",
                fallback="Theme.of(context).colorScheme.primary",
            )
            label_expr = _label_color_expr_for_filled_control(node, label_node)
            specs[label_node.text.strip()] = (background_expr, label_expr)

    for parent in _collect_all_nodes(clean_tree):
        background_node = next(
            (
                child
                for child in parent.children
                if child.type == NodeType.CONTAINER and child.style.background_color
            ),
            None,
        )
        if background_node is None:
            continue
        for child in parent.children:
            if child.type != NodeType.TEXT or not child.text:
                continue
            label = child.text.strip()
            if label in specs:
                continue
            background_expr = dart_color_expr(
                background_node.style,
                css_key="background-color",
                fallback="Theme.of(context).colorScheme.primary",
            )
            label_expr = _label_color_expr_for_filled_control(background_node, child)
            specs[label] = (background_expr, label_expr)
    return specs


def _collect_stack_filled_label_color_by_figma_id(
    clean_tree: CleanDesignTreeNode,
) -> dict[str, str]:
    """Map TEXT figma ids on filled stacks to Dart label color expressions."""
    specs: dict[str, str] = {}
    for parent in _collect_all_nodes(clean_tree):
        if parent.type != NodeType.STACK:
            continue
        fill_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.CONTAINER and child.style.background_color
        ]
        if not fill_nodes:
            continue
        background_node = fill_nodes[0]
        for child in parent.children:
            if child.type != NodeType.TEXT or not child.text:
                continue
            specs[child.id] = _label_color_expr_for_filled_control(background_node, child)
    for node in _collect_all_nodes(clean_tree):
        if node.type != NodeType.BUTTON:
            continue
        label_node = _first_text_descendant(node)
        if label_node is None:
            continue
        specs[label_node.id] = _label_color_expr_for_filled_control(node, label_node)
    return specs


def _patch_secondary_text_below_opaque_fill(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Move lower TEXT siblings below an opaque CONTAINER fill using stackPlacement only."""
    from figma_flutter_agent.generator.figma_anchor import figma_key_token

    updated = screen_code
    for parent in _collect_all_nodes(clean_tree):
        if parent.type != NodeType.STACK:
            continue
        fill_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.CONTAINER
            and child.style.background_color
            and child.stack_placement is not None
        ]
        text_nodes = [
            child
            for child in parent.children
            if child.type == NodeType.TEXT and child.text and child.stack_placement is not None
        ]
        if len(fill_nodes) != 1 or len(text_nodes) < 2:
            continue
        fill_node = fill_nodes[0]
        fill_placement = fill_node.stack_placement
        if fill_placement is None:
            continue
        fill_height = fill_placement.height or fill_node.sizing.height
        if fill_height is None:
            continue
        fill_top = float(fill_placement.top or 0.0)
        fill_bottom = fill_top + float(fill_height)
        ordered_texts = sorted(
            text_nodes,
            key=lambda node: float(node.stack_placement.top or 0.0),
        )
        primary_top = float(ordered_texts[0].stack_placement.top or 0.0)
        for secondary in ordered_texts[1:]:
            placement = secondary.stack_placement
            if placement is None or placement.top is None:
                continue
            secondary_top = float(placement.top)
            if secondary_top < primary_top + 2.0:
                continue
            if secondary_top >= fill_bottom - 2.0:
                continue
            target_top = fill_bottom + 4.0
            token = re.escape(figma_key_token(secondary.id))
            pattern = rf"(key:\s*ValueKey\('{token}'\)[\s\S]{{0,500}}?top:\s*)([\d.]+)"
            updated, _count = re.subn(
                pattern,
                lambda match, top=target_top: f"{match.group(1)}{top}",
                updated,
                count=1,
            )
    return updated


def _patch_stack_filled_buttons_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Fix label colors on InkWell/Stack buttons matched by Figma ValueKey or label copy."""
    from figma_flutter_agent.generator.figma_anchor import figma_key_token

    specs_by_id = _collect_stack_filled_label_color_by_figma_id(clean_tree)
    updated = screen_code
    for figma_id, label_expr in specs_by_id.items():
        token = re.escape(figma_key_token(figma_id))
        key_pattern = rf"key:\s*ValueKey\('{token}'\)"
        for key_match in re.finditer(key_pattern, updated):
            window_start = key_match.start()
            window_end = min(len(updated), key_match.end() + 2500)
            window = updated[window_start:window_end]
            if "BoxDecoration" not in window and "InkWell" not in window:
                continue
            from figma_flutter_agent.generator.dart.delimiters import (
                replace_first_copywith_color,
            )

            patched_window, replacements = replace_first_copywith_color(
                window,
                label_expr,
            )
            if not replacements:
                patched_window, replacements = re.subn(
                    r"color:\s*Color\([^)]+\)",
                    f"color: {label_expr}",
                    window,
                    count=1,
                )
            if replacements:
                updated = updated[:window_start] + patched_window + updated[window_end:]
                break

    specs = _collect_button_style_specs(clean_tree)
    if not specs:
        return updated
    for label, (_background_expr, label_expr) in specs.items():
        escaped = re.escape(label)
        for match in re.finditer(rf"Text\(\s*['\"]{escaped}['\"]", updated):
            context_start = max(0, match.start() - 4000)
            context_end = min(len(updated), match.end() + 900)
            context = updated[context_start:context_end]
            if "BoxDecoration" not in context and "InkWell" not in context:
                continue
            window_start = match.start()
            window = updated[window_start:context_end]
            from figma_flutter_agent.generator.dart.delimiters import (
                replace_first_copywith_color,
            )

            patched_window, did_patch = replace_first_copywith_color(window, label_expr)
            if not did_patch:
                patched_window, replacements = re.subn(
                    r"color:\s*Color\([^)]+\)",
                    f"color: {label_expr}",
                    window,
                    count=1,
                )
                did_patch = bool(replacements)
            if did_patch:
                updated = updated[:window_start] + patched_window + updated[context_end:]
                break
    return updated


def _patch_material_buttons_from_tree(screen_code: str, clean_tree: CleanDesignTreeNode) -> str:
    """Apply Figma fill/label colors to Material buttons matched by their visible label text."""
    specs = _collect_button_style_specs(clean_tree)
    if not specs:
        return screen_code

    updated = screen_code
    for label, (background_expr, label_expr) in specs.items():
        escaped_label = re.escape(label)
        for match in re.finditer(r"\b(?:FilledButton|ElevatedButton|TextButton)\s*\(", updated):
            button_start = match.start()
            paren_start = match.end() - 1
            paren_end = _find_matching_paren(updated, paren_start)
            if paren_end is None:
                continue
            block = updated[button_start : paren_end + 1]
            if not re.search(rf"['\"]{escaped_label}['\"]", block):
                continue
            patched = block
            for bg_pattern in (
                r"backgroundColor:\s*Theme\.of\(\s*context\s*\)\s*\.colorScheme\.primary",
                r"backgroundColor:\s*theme\.colorScheme\.primary",
            ):
                patched = re.sub(
                    bg_pattern,
                    f"backgroundColor: {background_expr}",
                    patched,
                    count=1,
                    flags=re.DOTALL,
                )
            label_style = re.search(
                rf"Text\(\s*['\"]{escaped_label}['\"][\s\S]*?TextStyle\(\s*color:\s*[^,\n)]+",
                patched,
                flags=re.DOTALL,
            )
            if label_style is not None:
                fixed_label = re.sub(
                    r"color:\s*[^,\n)]+",
                    f"color: {label_expr}",
                    label_style.group(0),
                    count=1,
                )
                patched = (
                    patched[: label_style.start()] + fixed_label + patched[label_style.end() :]
                )
            else:
                for color_pattern in (
                    r"color:\s*Theme\.of\(\s*context\s*\)\s*\.colorScheme\.onPrimary",
                    r"color:\s*theme\.colorScheme\.onPrimary",
                ):
                    patched = re.sub(
                        color_pattern,
                        f"color: {label_expr}",
                        patched,
                        count=1,
                        flags=re.DOTALL,
                    )
            updated = updated[:button_start] + patched + updated[paren_end + 1 :]
            break
    return updated


def _ensure_theme_color_scheme_in_scope(screen_code: str) -> str:
    """Use ``Theme.of(context).colorScheme`` when no local ``theme`` binding exists."""
    if "theme.colorScheme" not in screen_code:
        return screen_code
    has_local_theme = "final ThemeData theme =" in screen_code or (
        "ThemeData theme =" in screen_code and "return Theme(" in screen_code
    )
    if has_local_theme:
        return screen_code
    return screen_code.replace(
        "theme.colorScheme",
        "Theme.of(context).colorScheme",
    )


def _patch_theme_wrapped_color_scheme(screen_code: str) -> str:
    """Route colorScheme lookups through the local ``theme`` when the screen re-themes itself."""
    if not re.search(
        r"final\s+ThemeData\s+theme\s*=\s*Theme\.of\s*\(\s*context\s*\)",
        screen_code,
    ):
        return screen_code
    if "return Theme(" not in screen_code:
        return screen_code
    theme_start = screen_code.find("return Theme(")
    if theme_start == -1:
        return screen_code
    tail = screen_code[theme_start:]
    return screen_code[:theme_start] + tail.replace(
        "Theme.of(context).colorScheme",
        "theme.colorScheme",
    )
