"""Tests for write and snapshot pipeline stages."""

from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import AssetManifest
from figma_flutter_agent.stages.snapshot import SnapshotStageRequest, persist_generation_snapshot
from figma_flutter_agent.stages.write import WriteStageRequest, commit_planned_files
from figma_flutter_agent.sync import load_snapshot


def _write_pubspec(project_dir: Path) -> None:
    (project_dir / "pubspec.yaml").write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )


def test_commit_planned_files_writes_and_updates_pubspec(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_pubspec(project_dir)

    with patch("figma_flutter_agent.stages.write.validate_dart_project"):
        result = commit_planned_files(
            WriteStageRequest(
                project_dir=project_dir,
                files_to_write={"lib/main.dart": "void main() {}"},
                asset_manifest=AssetManifest(),
                routing_type="none",
                state_management_type="none",
            )
        )

    assert result.written_files == ["lib/main.dart"]
    assert (project_dir / "lib" / "main.dart").is_file()


def test_commit_planned_files_rolls_back_on_validation_failure(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_pubspec(project_dir)
    target = project_dir / "lib" / "main.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")

    with (
        patch(
            "figma_flutter_agent.stages.write.validate_dart_project",
            side_effect=GenerationError("analyze failed"),
        ),
        pytest.raises(GenerationError, match="analyze failed"),
    ):
        commit_planned_files(
            WriteStageRequest(
                project_dir=project_dir,
                files_to_write={"lib/main.dart": "void main() { broken"},
                asset_manifest=AssetManifest(),
                routing_type="none",
                state_management_type="none",
            )
        )

    assert target.read_text(encoding="utf-8") == "void main() {}"
    assert "flutter_svg" not in (project_dir / "pubspec.yaml").read_text(encoding="utf-8")


def test_persist_generation_snapshot_writes_sync_metadata(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    persist_generation_snapshot(
        SnapshotStageRequest(
            project_dir=project_dir,
            file_key="abc",
            node_id="1:1",
            feature_name="onboarding",
            tree_hash="tree",
            colors_hash="colors",
            typography_hash="typography",
            spacing_hash="spacing",
            planned_files={"lib/main.dart": "void main() {}"},
            reference_image_hash="ref",
        )
    )

    outcome = load_snapshot(project_dir)
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot
    assert snapshot.feature_name == "onboarding"
    assert snapshot.version == 1
    assert snapshot.file_hashes["lib/main.dart"]


def test_persist_generation_snapshot_increments_version(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    first = persist_generation_snapshot(
        SnapshotStageRequest(
            project_dir=project_dir,
            file_key="abc",
            node_id="1:1",
            feature_name="onboarding",
            tree_hash="tree",
            colors_hash="colors",
            typography_hash="typography",
            spacing_hash="spacing",
            planned_files={"lib/main.dart": "void main() {}"},
        )
    )
    second = persist_generation_snapshot(
        SnapshotStageRequest(
            project_dir=project_dir,
            file_key="abc",
            node_id="1:1",
            feature_name="onboarding",
            tree_hash="tree2",
            colors_hash="colors",
            typography_hash="typography",
            spacing_hash="spacing",
            planned_files={"lib/main.dart": "void main() {}"},
            expected_snapshot_version=first.version,
        )
    )
    assert second.version == first.version + 1
