"""Write-stage dart analyze scope (production all_planned vs incremental written_only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.generator.dart.project_validation import PlannedAnalyzeOutcome
from figma_flutter_agent.generator.writing.models import WriteBatch
from figma_flutter_agent.schemas import AssetManifest
from figma_flutter_agent.stages.write import WriteStageRequest, commit_planned_files


def test_write_all_planned_analyzes_full_plan_not_only_written_subset(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: demo_app\n", encoding="utf-8")
    files = {
        "lib/theme/app_colors.dart": "class AppColors {}",
        "lib/generated/screen_layout.dart": "class Layout {}",
    }
    (tmp_path / "lib" / "generated").mkdir(parents=True)
    (tmp_path / "lib" / "generated" / "screen_layout.dart").write_text(
        files["lib/generated/screen_layout.dart"],
        encoding="utf-8",
    )
    request = WriteStageRequest(
        project_dir=tmp_path,
        files_to_write={"lib/theme/app_colors.dart": files["lib/theme/app_colors.dart"]},
        asset_manifest=AssetManifest(),
        routing_type="go_router",
        state_management_type="none",
        enable_backup=False,
        require_dart_sdk=False,
        analyze_scope="all_planned",
        analyze_relative_paths=sorted(files.keys()),
    )

    with (
        patch("figma_flutter_agent.stages.write.update_pubspec"),
        patch("figma_flutter_agent.stages.write.analyze_planned_dart_files") as analyze,
        patch("figma_flutter_agent.stages.write.DartWriter") as writer_cls,
    ):
        analyze.return_value = PlannedAnalyzeOutcome(
            skipped=False,
            passed=True,
            detail="dart analyze passed",
        )
        writer = writer_cls.return_value
        writer.write_files.return_value = WriteBatch(backup_dir=tmp_path / ".bak", written=[])
        writer.commit_batch.return_value = None
        commit_planned_files(request)

    planned = analyze.call_args.args[0]
    assert set(planned.keys()) == {
        "lib/generated/screen_layout.dart",
        "lib/theme/app_colors.dart",
    }
    assert analyze.call_args.kwargs["analyze_scope"] == "all_planned"


def test_write_preserves_minified_layout_on_disk(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: demo_app\n", encoding="utf-8")
    minified_body = "void main() {" + ", ".join("Text('x')" for _ in range(900)) + "}"
    request = WriteStageRequest(
        project_dir=tmp_path,
        files_to_write={"lib/generated/screen_layout.dart": minified_body},
        asset_manifest=AssetManifest(),
        routing_type="none",
        state_management_type="none",
        enable_backup=False,
        require_dart_sdk=False,
        analyze_scope="written_only",
    )

    with (
        patch("figma_flutter_agent.stages.write.update_pubspec"),
        patch("figma_flutter_agent.stages.write.analyze_planned_dart_files") as analyze,
        patch("figma_flutter_agent.stages.write.DartWriter") as writer_cls,
    ):
        analyze.return_value = PlannedAnalyzeOutcome(
            skipped=False,
            passed=True,
            detail="dart analyze passed",
        )
        writer = writer_cls.return_value
        writer.write_files.return_value = WriteBatch(backup_dir=tmp_path / ".bak", written=[])
        writer.commit_batch.return_value = None
        commit_planned_files(request)

    written_content = writer.write_files.call_args.args[0]["lib/generated/screen_layout.dart"]
    assert written_content == minified_body
