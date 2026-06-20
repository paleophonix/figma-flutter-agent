"""Tests for orchestrator-injected repair read-step prompts."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.dev.opencode.prompt_context import build_read_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain


def test_forensic_recognise_injects_hot_bundle(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    mirror = worktree / ".repair" / "debug" / "limbo" / "sign_up"
    mirror.mkdir(parents=True)
    (mirror / "run_manifest.json").write_text(
        json.dumps({"verdict": "CANDIDATE_ONLY", "writeback": "committed"}),
        encoding="utf-8",
    )
    (mirror / "dart-errors.json").write_text(
        json.dumps([{"code": "uri_does_not_exist", "message": "missing layout"}]),
        encoding="utf-8",
    )
    (mirror / "last.log").write_text("analyze failed\n", encoding="utf-8")

    chain = ReasoningChain()
    prompt = build_read_step_user_prompt(
        "recognise",
        feature="sign_up",
        board="forensic",
        worktree=worktree,
        debug_mirror=mirror,
        chain=chain,
    )

    assert "CANDIDATE_ONLY" in prompt
    assert "uri_does_not_exist" in prompt
    assert "analyze failed" in prompt
    assert "do not claim files are missing" in prompt


def test_diagnose_injects_chain_and_artifact_refs(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    mirror = worktree / ".repair" / "debug" / "limbo" / "sign_up"
    mirror.mkdir(parents=True)
    (mirror / "dart-errors.json").write_text("[]", encoding="utf-8")
    (mirror / "last.log").write_text("tail", encoding="utf-8")
    ref_path = mirror / "screen.dart"
    ref_path.write_text("class SignUp {}", encoding="utf-8")

    chain = ReasoningChain()
    chain.append(
        "recognise",
        {"blocked": False, "symptoms": [{"id": "S1", "description": "missing import"}]},
    )
    chain.append(
        "inspect",
        {
            "blocked": False,
            "entities": [
                {
                    "id": "E1",
                    "artifactRefs": [".repair/debug/limbo/sign_up/screen.dart"],
                }
            ],
        },
    )

    prompt = build_read_step_user_prompt(
        "diagnose",
        feature="sign_up",
        board="forensic",
        worktree=worktree,
        debug_mirror=mirror,
        chain=chain,
    )

    assert "missing import" in prompt
    assert "class SignUp" in prompt
    assert "reasoning_chain" in prompt
