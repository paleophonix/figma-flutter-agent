"""Bottom navigation chrome helper injection."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.navigation.helpers import (
    bottom_nav_stateful_helpers,
    pill_nav_stateful_helpers,
)

_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+(?!_LayoutChromeNav)(?!_LayoutPillNav)(\w+)\s+extends\s+(?:Stateless|Stateful)Widget\b"
)


def ensure_layout_chrome_nav_helpers(
    source: str,
    *,
    theme_variant: str = "material_3",
) -> str:
    """Inject private bottom-nav helpers into widget libraries that reference them."""
    needs_chrome = "_LayoutChromeNav(" in source
    needs_pill = "_LayoutPillNav(" in source
    if not needs_chrome and not needs_pill:
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
    if "app_layout.dart" not in source and (
        "_LayoutChromeNav(" in source or "_LayoutPillNav(" in source
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
