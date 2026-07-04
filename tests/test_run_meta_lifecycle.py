"""run.meta.json lifecycle tests (Program 10 P0-2)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.run_meta import (
    LEGACY_RUN_META_SCHEMA_VERSION,
    RUN_META_SCHEMA_VERSION,
    begin_run_meta,
    mark_run_meta_failed,
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


def test_begin_run_meta_resets_candidate_preserves_committed(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-committed",
        writeback="committed",
        written_files=["lib/screens/home.dart"],
    )
    begin_run_meta(project, "home", pipeline_run_id="run-candidate")
    payload = json.loads(run_meta_path(project, "home").read_text(encoding="utf-8"))
    assert payload["candidate_build_run_id"] == "run-candidate"
    assert payload["committed_build_run_id"] == "run-committed"
    assert payload["status"] == "started"


def test_skipped_writeback_does_not_advance_committed(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-committed",
        writeback="committed",
        written_files=["lib/screens/home.dart"],
    )
    begin_run_meta(project, "home", pipeline_run_id="run-candidate")
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-candidate",
        writeback="skipped",
        written_files=[],
    )
    payload = json.loads(run_meta_path(project, "home").read_text(encoding="utf-8"))
    assert payload["committed_build_run_id"] == "run-committed"
    assert payload["candidate_build_run_id"] == "run-candidate"
    assert payload["writeback"] == "skipped"


def test_begin_run_meta_clears_candidate_evidence(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-old",
        writeback="committed",
        written_files=["lib/screens/home.dart"],
        committed_build_run_id="run-old",
        analyze_passed=True,
        cached_ir_verdict="compatible",
        clean_tree_hash="tree-old",
        generation_config_hash="cfg-old",
    )
    path = run_meta_path(project, "home")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "}",
            ', "last_error": "boom", "customField": "keep-me"}',
            1,
        ),
        encoding="utf-8",
    )
    begin_run_meta(project, "home", pipeline_run_id="run-new")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["candidate_build_run_id"] == "run-new"
    assert payload["committed_build_run_id"] == "run-old"
    assert payload["status"] == "started"
    assert "writeback" not in payload
    assert "written_files" not in payload
    assert "analyze_passed" not in payload
    assert "cached_ir_verdict" not in payload
    assert "clean_tree_hash" not in payload
    assert "generation_config_hash" not in payload
    assert "last_error" not in payload
    assert payload["customField"] == "keep-me"


def test_mark_run_meta_failed_sets_forensic_writeback(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "home",
        pipeline_run_id="run-committed",
        writeback="committed",
        written_files=["lib/screens/home.dart"],
        committed_build_run_id="run-committed",
    )
    mark_run_meta_failed(
        project,
        "home",
        pipeline_run_id="run-failed",
        error="boom",
    )
    payload = json.loads(run_meta_path(project, "home").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["writeback"] == "failed"
    assert payload["candidate_build_run_id"] == "run-failed"
    assert payload["committed_build_run_id"] == "run-committed"
    assert payload["written_files"] == []
    assert payload["last_error"] == "boom"


def test_mark_run_meta_failed_preserves_current_run_evidence(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "home", pipeline_run_id="run-fail")
    update_run_meta_stage(
        project,
        "home",
        pipeline_run_id="run-fail",
        status="planned",
        clean_tree_hash="tree-1",
        generation_config_hash="cfg-1",
        cached_ir_verdict="incompatible",
    )
    mark_run_meta_failed(project, "home", pipeline_run_id="run-fail", error="late fail")
    payload = json.loads(run_meta_path(project, "home").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["writeback"] == "failed"
    assert payload["clean_tree_hash"] == "tree-1"
    assert payload["generation_config_hash"] == "cfg-1"
    assert payload["cached_ir_verdict"] == "incompatible"
