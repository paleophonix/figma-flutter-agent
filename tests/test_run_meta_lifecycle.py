"""run.meta.json lifecycle tests (Program 10 P0-2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.debug.run_meta import (
    LEGACY_RUN_META_SCHEMA_VERSION,
    RUN_META_SCHEMA_VERSION,
    begin_run_meta,
    mark_run_meta_failed,
    read_run_meta,
    reconcile_run_meta_feature_identity,
    run_meta_path,
    update_run_meta_stage,
    write_run_meta,
)
from figma_flutter_agent.errors import RunMetaStaleWriterError


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
        json.dumps({"customField": "keep-me", "pipeline_run_id": "run-2"}),
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
    begin_run_meta(project, "home", pipeline_run_id="run-failed")
    update_run_meta_stage(
        project,
        "home",
        pipeline_run_id="run-failed",
        status="planned",
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


def test_stale_pipeline_run_id_cannot_update_run_meta(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "home", pipeline_run_id="run-new")
    with pytest.raises(RunMetaStaleWriterError, match="ownership mismatch"):
        update_run_meta_stage(
            project,
            "home",
            pipeline_run_id="run-old",
            status="parsed",
        )


def test_stale_pipeline_run_id_cannot_finalize_run_meta(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "home", pipeline_run_id="run-new")
    with pytest.raises(RunMetaStaleWriterError, match="ownership mismatch"):
        write_run_meta(
            project,
            "home",
            pipeline_run_id="run-old",
            writeback="skipped",
        )


def test_reconcile_run_meta_feature_identity_migrates_to_resolved(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "checkout", pipeline_run_id="run-1")
    canonical = reconcile_run_meta_feature_identity(
        project,
        pipeline_run_id="run-1",
        early_feature="checkout",
        resolved_feature="payment_screen",
    )
    assert canonical == "payment_screen"
    assert not run_meta_path(project, "checkout").is_file()
    record = read_run_meta(project, "payment_screen")
    assert record is not None
    assert record.pipeline_run_id == "run-1"
    assert record.candidate_build_run_id == "run-1"
    assert record.status == "started"


def test_reconcile_preserves_committed_and_extension_fields(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_run_meta(
        project,
        "checkout",
        pipeline_run_id="run-old",
        writeback="committed",
        committed_build_run_id="run-old",
        status="completed",
    )
    checkout_path = run_meta_path(project, "checkout")
    payload = json.loads(checkout_path.read_text(encoding="utf-8"))
    payload["customField"] = "keep-me"
    checkout_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    begin_run_meta(project, "checkout", pipeline_run_id="run-new")
    reconcile_run_meta_feature_identity(
        project,
        pipeline_run_id="run-new",
        early_feature="checkout",
        resolved_feature="payment_screen",
    )

    assert not run_meta_path(project, "checkout").is_file()
    migrated = json.loads(run_meta_path(project, "payment_screen").read_text(encoding="utf-8"))
    assert migrated["pipeline_run_id"] == "run-new"
    assert migrated["candidate_build_run_id"] == "run-new"
    assert migrated["committed_build_run_id"] == "run-old"
    assert migrated["customField"] == "keep-me"
    assert migrated["status"] == "started"


def test_reconcile_stale_when_canonical_target_owned_by_newer_run(tmp_path: Path) -> None:
    """Slow alias run A must not steal canonical metadata from newer run B."""
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "checkout", pipeline_run_id="run-a")
    begin_run_meta(project, "payment_screen", pipeline_run_id="run-b")

    with pytest.raises(RunMetaStaleWriterError, match="superseded"):
        reconcile_run_meta_feature_identity(
            project,
            pipeline_run_id="run-a",
            early_feature="checkout",
            resolved_feature="payment_screen",
        )

    record = read_run_meta(project, "payment_screen")
    assert record is not None
    assert record.pipeline_run_id == "run-b"
    assert run_meta_path(project, "checkout").is_file()


def test_reconcile_stale_when_canonical_completed_by_newer_run(tmp_path: Path) -> None:
    """Alias run A must not roll back a newer completed canonical run B."""
    import time

    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "checkout", pipeline_run_id="run-a")
    time.sleep(0.05)
    begin_run_meta(project, "payment_screen", pipeline_run_id="run-b")
    write_run_meta(
        project,
        "payment_screen",
        pipeline_run_id="run-b",
        writeback="committed",
        committed_build_run_id="run-b",
        status="completed",
    )

    with pytest.raises(RunMetaStaleWriterError, match="superseded"):
        reconcile_run_meta_feature_identity(
            project,
            pipeline_run_id="run-a",
            early_feature="checkout",
            resolved_feature="payment_screen",
        )

    record = read_run_meta(project, "payment_screen")
    assert record is not None
    assert record.pipeline_run_id == "run-b"
    assert record.status == "completed"
    assert record.committed_build_run_id == "run-b"


def test_reconcile_rejects_missing_source_artifact(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "checkout", pipeline_run_id="run-a")
    run_meta_path(project, "checkout").unlink()

    with pytest.raises(RunMetaStaleWriterError, match="missing alias source"):
        reconcile_run_meta_feature_identity(
            project,
            pipeline_run_id="run-a",
            early_feature="checkout",
            resolved_feature="payment_screen",
        )


def test_reconcile_prefers_canonical_committed_over_alias_source(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    target_path = run_meta_path(project, "payment_screen")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(
            {
                "feature": "payment_screen",
                "pipeline_run_id": "run-hist",
                "candidate_build_run_id": "run-hist",
                "committed_build_run_id": "run-canonical",
                "writeback": "committed",
                "written_files": [],
                "analyze_passed": True,
                "captured_at": "2020-01-01T00:00:00+00:00",
                "run_started_at": "2020-01-01T00:00:00+00:00",
                "runMetaSchemaVersion": "2",
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )

    begin_run_meta(project, "checkout", pipeline_run_id="run-new")
    source_path = run_meta_path(project, "checkout")
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    source_payload["committed_build_run_id"] = "run-alias"
    source_path.write_text(json.dumps(source_payload, indent=2), encoding="utf-8")

    reconcile_run_meta_feature_identity(
        project,
        pipeline_run_id="run-new",
        early_feature="checkout",
        resolved_feature="payment_screen",
    )

    migrated = json.loads(run_meta_path(project, "payment_screen").read_text(encoding="utf-8"))
    assert migrated["committed_build_run_id"] == "run-canonical"
    assert migrated["pipeline_run_id"] == "run-new"


def test_overlapping_runs_stale_writer_cannot_corrupt_newer(tmp_path: Path) -> None:
    """Run A began, run B claimed the screen; A must not overwrite B's metadata."""
    project = tmp_path / "demo"
    project.mkdir()
    begin_run_meta(project, "home", pipeline_run_id="run-a")
    begin_run_meta(project, "home", pipeline_run_id="run-b")
    with pytest.raises(RunMetaStaleWriterError, match="ownership mismatch"):
        update_run_meta_stage(
            project,
            "home",
            pipeline_run_id="run-a",
            status="parsed",
        )
    with pytest.raises(RunMetaStaleWriterError, match="ownership mismatch"):
        write_run_meta(
            project,
            "home",
            pipeline_run_id="run-a",
            writeback="committed",
        )
    record = read_run_meta(project, "home")
    assert record is not None
    assert record.pipeline_run_id == "run-b"
    assert record.candidate_build_run_id == "run-b"
    assert record.status == "started"
