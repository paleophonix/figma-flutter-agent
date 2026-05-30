"""Golden capture enrichment from live Flutter projects."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.planned_dart import _widget_lib_path_for_class
from figma_flutter_agent.validation.golden_capture_enrich import (
    enrich_planned_from_project,
    sync_pubspec_asset_directories,
)


def test_widget_lib_path_for_class() -> None:
    assert _widget_lib_path_for_class("Group17Widget") == "lib/widgets/group17_widget.dart"
    assert _widget_lib_path_for_class("GroupWidget") == "lib/widgets/group_widget.dart"


def test_enrich_replaces_inline_shrink_stub_with_project_widget(tmp_path: Path) -> None:
    project = tmp_path / "project"
    widget_path = project / "lib" / "widgets" / "group_widget.dart"
    widget_path.parent.mkdir(parents=True)
    widget_path.write_text(
        "import 'package:flutter/material.dart';\n"
        "import 'package:flutter_svg/flutter_svg.dart';\n"
        "class GroupWidget extends StatelessWidget {\n"
        "  const GroupWidget({super.key});\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return SvgPicture.asset('assets/icons/hero.svg');\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    screen_path = "lib/features/demo/demo_screen.dart"
    planned = {
        screen_path: (
            "import 'package:flutter/material.dart';\n"
            "class DemoScreen extends StatelessWidget {\n"
            "  const DemoScreen({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return const GroupWidget();\n"
            "  }\n"
            "}\n"
            "class GroupWidget extends StatelessWidget {\n"
            "  const GroupWidget({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return const SizedBox.shrink();\n"
            "  }\n"
            "}\n"
        ),
    }
    enriched = enrich_planned_from_project(planned, project)
    assert "lib/widgets/group_widget.dart" in enriched
    assert "SvgPicture.asset" in enriched["lib/widgets/group_widget.dart"]
    assert "class GroupWidget extends StatelessWidget" not in enriched[screen_path]
    assert "package:demo_app/widgets/group_widget.dart" in enriched[screen_path] or (
        "widgets/group_widget.dart" in enriched[screen_path]
    )


def test_sync_pubspec_asset_directories_copies_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    capture = tmp_path / "capture"
    icons = source / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "a.svg").write_text("<svg/>", encoding="utf-8")
    (source / "pubspec.yaml").write_text(
        "name: demo\nflutter:\n  assets:\n    - assets/icons/\n",
        encoding="utf-8",
    )
    sync_pubspec_asset_directories(capture, source)
    assert (capture / "assets" / "icons" / "a.svg").is_file()
