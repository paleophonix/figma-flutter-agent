"""Tests for EffectiveBuildIdentity proof kinds."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import RUN_META_JSON
from figma_flutter_agent.dev.opencode.build_identity import reevaluate_build_identity
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult


def _gate(tmp_path: Path) -> RunGateResult:
    root = tmp_path / "screen"
    root.mkdir(parents=True)
    return RunGateResult(
        feature="login",
        screen_root=root,
        verdict=FailureClass.NO_SERVE,
        case_mode="FORENSIC",
        agent_board="forensic",
        pipeline_run_id="old-run",
        candidate_build_run_id="old-run",
        committed_build_run_id="old-run",
        served_build_run_id="stale-served",
        writeback="skipped",
        served_probe_present=False,
        candidate_available=False,
        manifest_path=root / "run_manifest.json",
        allowed_questions=(),
        forbidden_questions=(),
    )


def test_reevaluate_build_identity_uses_regen_run_id_not_stale_gate(
    tmp_path: Path,
) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "screen.dart").write_text("// FFA_RUN_ID: fresh-run\n", encoding="utf-8")
    (mirror / RUN_META_JSON).write_text(
        json.dumps(
            {
                "pipeline_run_id": "fresh-run",
                "committed_build_run_id": "fresh-run",
                "writeback": "committed",
            }
        ),
        encoding="utf-8",
    )

    identity = reevaluate_build_identity(
        mirror,
        project_dir=tmp_path / "project",
        feature="login",
        initial_gate=_gate(tmp_path),
        regenerate_payload={"passed": True, "run_id": "fresh-run"},
    )

    assert identity.proof_kind == "served_probe"
    assert identity.served_run_id == "fresh-run"
    assert identity.committed_run_id == "fresh-run"
    assert identity.served_run_id != "stale-served"
