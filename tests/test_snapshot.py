import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.sync.snapshot import GenerationSnapshot, load_snapshot, snapshot_path

_FEATURE = "home"


def test_load_snapshot_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    path = snapshot_path(tmp_path, _FEATURE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    outcome = load_snapshot(tmp_path, _FEATURE)

    assert outcome.snapshot is None
    assert outcome.quarantined_path is not None
    assert not path.exists()
    assert path.with_suffix(".json.corrupt").is_file()


def test_load_snapshot_fail_on_corrupt_raises(tmp_path: Path) -> None:
    path = snapshot_path(tmp_path, _FEATURE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(FlutterProjectError, match="quarantined"):
        load_snapshot(tmp_path, _FEATURE, fail_on_corrupt=True)


def test_load_snapshot_returns_snapshot_for_valid_file(tmp_path: Path) -> None:
    path = snapshot_path(tmp_path, _FEATURE)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = GenerationSnapshot(
        file_key="abc",
        node_id="1:1",
        feature_name=_FEATURE,
        tree_hash="tree",
        colors_hash="colors",
        typography_hash="typography",
        spacing_hash="spacing",
    )
    path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")

    outcome = load_snapshot(tmp_path, _FEATURE)

    assert outcome.snapshot is not None
    assert outcome.snapshot.file_key == "abc"
