"""Tests for manifest-backed offline dump resolution."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.pipeline.helpers import resolve_manifest_cached_dump


def test_resolve_manifest_cached_dump_by_feature(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    dump_path = project / ".debug" / "raw" / "sleep_music_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text(json.dumps({"id": "3:3216", "type": "FRAME"}), encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: sleep_music",
                "    node_id: 3:3216",
                "    dump: .debug/raw/sleep_music_layout.json",
            ]
        ),
        encoding="utf-8",
    )

    resolved = resolve_manifest_cached_dump(project, feature_name="sleep_music")

    assert resolved == dump_path


def test_resolve_manifest_cached_dump_by_node_id(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    dump_path = project / ".debug" / "raw" / "sleep_music_layout.json"
    dump_path.parent.mkdir(parents=True)
    dump_path.write_text("{}", encoding="utf-8")
    (project / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: sleep_music",
                "    node_id: 3:3216",
                "    dump: .debug/raw/sleep_music_layout.json",
            ]
        ),
        encoding="utf-8",
    )

    resolved = resolve_manifest_cached_dump(
        project,
        node_id="3:3216",
        file_key="abc123",
    )

    assert resolved == dump_path
