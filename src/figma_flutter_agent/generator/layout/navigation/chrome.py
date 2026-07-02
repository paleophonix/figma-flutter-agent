"""Bottom navigation chrome helper injection."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.navigation.helpers import (
    bottom_nav_stateful_helpers,
    icon_nav_stateful_helpers,
    pill_nav_stateful_helpers,
)

_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+(?!_LayoutChromeNav)(?!_LayoutPillNav)(?!_LayoutIconNav)(\w+)\s+extends\s+(?:Stateless|Stateful)Widget\b"
)

_ICON_NAV_HELPER_MARKERS = (
    "required this.slotWidth",
    "required this.rowBandHeight",
    "required this.activePillRadius",
    "clipBehavior: Clip.none",
    "OverflowBox(",
    "width: tab.iconWidth",
    "HitTestBehavior.opaque",
)
_ICON_NAV_TAB_SPEC_MARKER = "class _IconNavTabSpec {"
_ICON_NAV_STATE_MARKER = "class _LayoutIconNavState extends State<_LayoutIconNav>"


def icon_nav_helpers_need_refresh(source: str) -> bool:
    """True when icon-nav call sites need helpers newer than the embedded blob."""
    if "_LayoutIconNav(" not in source:
        return False
    if "class _LayoutIconNav extends StatefulWidget" not in source:
        return True
    return any(marker not in source for marker in _ICON_NAV_HELPER_MARKERS)


def _strip_icon_nav_stateful_helpers(source: str) -> str:
    """Remove a stale icon-nav helper block so a fresh blob can be injected."""
    start = source.find(_ICON_NAV_TAB_SPEC_MARKER)
    if start < 0:
        return source
    state_start = source.find(_ICON_NAV_STATE_MARKER, start)
    if state_start < 0:
        return source
    brace_start = source.find("{", state_start + len(_ICON_NAV_STATE_MARKER))
    if brace_start < 0:
        return source
    depth = 0
    index = brace_start
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                while end < len(source) and source[end] in "\r\n":
                    end += 1
                return f"{source[:start]}{source[end:]}"
        index += 1
    return source


def _inject_icon_nav_stateful_helpers(source: str) -> str:
    """Insert the current icon-nav helper blob before the first public widget class."""
    decl = _WIDGET_CLASS_DECL_RE.search(source)
    if decl is None:
        return source
    helpers = icon_nav_stateful_helpers(node_id="widget-bottom-nav")
    return f"{source[: decl.start()]}{helpers}\n{source[decl.start() :]}"


def ensure_layout_chrome_nav_helpers(
    source: str,
    *,
    theme_variant: str = "material_3",
) -> str:
    """Inject private bottom-nav helpers into widget libraries that reference them."""
    needs_chrome = "_LayoutChromeNav(" in source
    needs_pill = "_LayoutPillNav(" in source
    needs_icon = "_LayoutIconNav(" in source
    if not needs_chrome and not needs_pill and not needs_icon:
        return source
    if needs_chrome and "class _LayoutChromeNav extends StatefulWidget" not in source:
        decl = _WIDGET_CLASS_DECL_RE.search(source)
        if decl is not None:
            helpers = bottom_nav_stateful_helpers(
                theme_variant=theme_variant,
                node_id="widget-bottom-nav",
            )
            source = f"{source[: decl.start()]}{helpers}\n{source[decl.start() :]}"
    if needs_pill and "class _LayoutPillNav extends StatefulWidget" not in source:
        decl = _WIDGET_CLASS_DECL_RE.search(source)
        if decl is not None:
            helpers = pill_nav_stateful_helpers(node_id="widget-bottom-nav")
            source = f"{source[: decl.start()]}{helpers}\n{source[decl.start() :]}"
    if needs_icon and icon_nav_helpers_need_refresh(source):
        source = _strip_icon_nav_stateful_helpers(source)
        source = _inject_icon_nav_stateful_helpers(source)
    if "app_layout.dart" not in source and (
        "_LayoutChromeNav(" in source or "_LayoutPillNav(" in source or "_LayoutIconNav(" in source
    ):
        package_name = "demo_app"
        package_match = re.search(r"import 'package:([^/]+)/theme/", source)
        if package_match is not None:
            package_name = package_match.group(1)
        material_import = re.search(
            r"import 'package:flutter/material.dart';\n",
            source,
        )
        if material_import is not None:
            layout_import = f"import 'package:{package_name}/theme/app_layout.dart';\n"
            insert_at = material_import.end()
            source = f"{source[:insert_at]}{layout_import}{source[insert_at:]}"
    return source
