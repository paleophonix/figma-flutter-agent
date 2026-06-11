"""Tests for pubspec package inference from generated Dart imports."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.package_name import (
    infer_project_package_name,
    infer_project_package_name_from_sources,
)


def test_infer_project_package_name_prefers_theme_import_over_flutter_svg() -> None:
    source = (
        "import 'package:flutter/material.dart';\n"
        "import 'package:flutter_svg/flutter_svg.dart';\n"
        "import 'package:acme_ui/theme/app_colors.dart';\n"
    )
    assert infer_project_package_name(source) == "acme_ui"


def test_infer_project_package_name_falls_back_when_only_external_deps() -> None:
    source = (
        "import 'package:flutter/material.dart';\n"
        "import 'package:flutter_svg/flutter_svg.dart';\n"
    )
    assert infer_project_package_name(source, default="demo_app") == "demo_app"


def test_infer_project_package_name_from_sources_scans_batch() -> None:
    sources = [
        "import 'package:flutter/material.dart';\n",
        "import 'package:go_router/go_router.dart';\n",
        "import 'package:batch_app/widgets/foo_widget.dart';\n",
    ]
    assert infer_project_package_name_from_sources(sources) == "batch_app"
