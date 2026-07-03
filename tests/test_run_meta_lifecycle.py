"""run.meta.json lifecycle tests (Program 10 P0-2)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.run_meta import (
    LEGACY_RUN_META_SCHEMA_VERSION,
    RUN_META_SCHEMA_VERSION,
    read_run_meta,
    run_meta_path,
    update_run_meta_stage,
    write_run_meta,
)


def test_run_meta_roundtrip_with_extended_fields(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-1",
        writeback="skipped",
        cached_ir_verdict="compatible",
        clean_tree_hash="hash-1",
        generation_config_hash="cfg-1",
    )
    record = read_run_meta(project, "home")
    assert record is not None
    assert record.run_meta_schema_version == RUN_META_SCHEMA_VERSION
    assert record.status == "completed"
    assert record.cached_ir_verdict == "compatible"
    raw = json.loads(run_meta_path(project, "home").read_text(encoding="utf-8"))
    assert raw["runMetaSchemaVersion"] == RUN_META_SCHEMA_VERSION


def test_legacy_run_meta_not_upgraded_to_completed(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    path = run_meta_path(project, "home")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "feature": "home",
                "pipeline_run_id": "legacy-run",
                "writeback": "skipped",
            }
        ),
        encoding="utf-8",
    )
    record = read_run_meta(project, "home")
    assert record is not None
    assert record.run_meta_schema_version == LEGACY_RUN_META_SCHEMA_VERSION
    assert record.status == "legacy"


def test_update_run_meta_stage_preserves_unknown_fields(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    path = run_meta_path(project, "home")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"customField": "keep-me", "pipeline_run_id": "old"}),
        encoding="utf-8",
    )
    update_run_meta_stage(
        project,
        "home",
        pipeline_run_id="run-2",
        status="parsed",
        clean_tree_hash="abc",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["customField"] == "keep-me"
    assert payload["status"] == "parsed"
    assert payload["runMetaSchemaVersion"] == RUN_META_SCHEMA_VERSION
