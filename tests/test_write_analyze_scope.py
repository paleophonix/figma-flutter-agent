"""Write-stage dart analyze scope (production all_planned vs incremental written_only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.generator.writer import WriteBatch
from figma_flutter_agent.schemas import AssetManifest
from figma_flutter_agent.stages.write import WriteStageRequest, commit_planned_files


def test_write_all_planned_analyzes_full_plan_not_only_written_subset(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: demo_app\n", encoding="utf-8")
    files = {
        "lib/theme/app_colors.dart": "class AppColors {}",
        "lib/generated/screen_layout.dart": "class Layout {}",
    }
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
        patch("figma_flutter_agent.stages.write.validate_dart_project") as validate,
        patch("figma_flutter_agent.stages.write.DartWriter") as writer_cls,
    ):
        writer = writer_cls.return_value
        writer.write_files.return_value = WriteBatch(backup_dir=tmp_path / ".bak", written=[])
        writer.commit_batch.return_value = None
        commit_planned_files(request)

    paths = validate.call_args.kwargs["relative_paths"]
    assert paths == ["lib/generated/screen_layout.dart", "lib/theme/app_colors.dart"]
    assert validate.call_args.kwargs["analyze_scope"] == "all_planned"
