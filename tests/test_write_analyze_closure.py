"""Write-stage analyze workspace must prefer planned catalog over disk fossils."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.dart.project_validation.write_analyze import (
    resolve_planned_for_write_analyze,
)


def test_resolve_planned_for_write_analyze_prefers_catalog_over_disk(tmp_path: Path) -> None:
    widget_path = "lib/widgets/section_header_widget.dart"
    fossil = (
        "import 'package:inbox/widgets/clusterd2e87d01_widget.dart';\n"
        "class SectionHeaderWidget {}\n"
    )
    catalog_body = "class SectionHeaderWidget { const SizedBox.shrink(); }\n"
    disk_file = tmp_path / widget_path
    disk_file.parent.mkdir(parents=True, exist_ok=True)
    disk_file.write_text(fossil, encoding="utf-8")

    resolved = resolve_planned_for_write_analyze(
        [widget_path],
        files_to_write={},
        planned_catalog={widget_path: catalog_body},
        project_dir=tmp_path,
        package_name="inbox",
    )

    assert resolved[widget_path] == catalog_body
    assert "clusterd2e87d01" not in resolved[widget_path]


def test_resolve_planned_for_write_analyze_falls_back_to_disk_when_not_in_catalog(
    tmp_path: Path,
) -> None:
    widget_path = "lib/widgets/legacy_widget.dart"
    disk_body = "class LegacyWidget {}\n"
    disk_file = tmp_path / widget_path
    disk_file.parent.mkdir(parents=True, exist_ok=True)
    disk_file.write_text(disk_body, encoding="utf-8")

    resolved = resolve_planned_for_write_analyze(
        [widget_path],
        files_to_write={},
        planned_catalog=None,
        project_dir=tmp_path,
        package_name="inbox",
    )

    assert resolved[widget_path] == disk_body
