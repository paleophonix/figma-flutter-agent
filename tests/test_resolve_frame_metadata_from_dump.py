"""Tests for offline dump metadata resolution without --figma-url."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.pipeline.dump import resolve_frame_metadata_from_dump


def test_resolve_frame_metadata_by_feature_and_dump_path(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    dump_path = project / ".debug" / "raw" / "background_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text(json.dumps({"id": "362:319", "type": "FRAME"}), encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: b40A9U0kfv6fLrtRIUQ4XM",
                "project_dir: .",
                "screens:",
                "  - feature: background",
                "    node_id: 362:319",
                "    dump: .debug/raw/background_layout.json",
            ]
        ),
        encoding="utf-8",
    )

    meta = resolve_frame_metadata_from_dump(project, dump_path)

    assert meta.file_key == "b40A9U0kfv6fLrtRIUQ4XM"
    assert meta.node_id == "362:319"
    assert meta.feature_name == "background"


def _write_minimal_pubspec(project: Path) -> None:
    (project / "pubspec.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )


def test_resolve_frame_metadata_infers_feature_from_filename(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    _write_minimal_pubspec(project)
    dump_path = project / ".debug" / "raw" / "sign_in_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text(json.dumps({"id": "1:3570", "type": "FRAME"}), encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc",
                "project_dir: .",
                "screens:",
                "  - feature: sign_in",
                "    node_id: 1:3570",
            ]
        ),
        encoding="utf-8",
    )

    meta = resolve_frame_metadata_from_dump(project, dump_path)

    assert meta.file_key == "abc"
    assert meta.node_id == "1:3570"
    assert meta.feature_name == "sign_in"


def test_resolve_frame_metadata_requires_manifest_for_file_key(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    _write_minimal_pubspec(project)
    dump_path = project / "raw.json"
    dump_path.write_text(json.dumps({"id": "1:2"}), encoding="utf-8")

    with pytest.raises(FlutterProjectError, match="file_key"):
        resolve_frame_metadata_from_dump(project, dump_path)
