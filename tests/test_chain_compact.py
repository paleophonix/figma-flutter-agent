"""Tests for executive reasoning-chain compaction."""

from __future__ import annotations

import json

from figma_flutter_agent.dev.opencode.chain_compact import compact_chain_for_step
from figma_flutter_agent.dev.opencode.prompt_context import build_read_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain

_REPEAT_SYMPTOM = (
    "Capture phase failed: Flutter capture test exited with code 1 due to a "
    "RenderFlex overflow by 1.5 pixels. The generated Row widget at "
    "login_version_1_layout.dart:42:9633 caused overflow."
)


def _bloated_chain() -> ReasoningChain:
    chain = ReasoningChain()
    chain.append(
        "recognise",
        {
            "blocked": False,
            "symptoms": [{"id": "S1", "description": _REPEAT_SYMPTOM}],
        },
    )
    chain.append(
        "inspect",
        {
            "blocked": False,
            "entities": [
                {
                    "id": f"entity-{index:03d}",
                    "relatesToSymptoms": [_REPEAT_SYMPTOM],
                    "kind": "pipeline_module",
                    "role": "capture",
                    "artifactRefs": [
                        ".repair/debug/limbo/login_version_1/run_manifest.json",
                        ".repair/debug/limbo/login_version_1/last.log",
                    ],
                    "repoPaths": ["debug/capture.py"],
                    "summary": _REPEAT_SYMPTOM + " " * 400,
                    "confidence": "high",
                    "blocked": False,
                }
                for index in range(1, 6)
            ],
        },
    )
    chain.append(
        "diagnose",
        {
            "blocked": False,
            "escalate": False,
            "laws": [
                {
                    "id": "law-fx-overflow-row-mainaxis-sizing",
                    "priority": "P0",
                    "layer": "generator/layout/widgets/emit/flex.py",
                    "entityIds": ["entity-001"],
                    "relatesToSymptoms": [_REPEAT_SYMPTOM],
                    "evidence": [
                        {
                            "ref": ".repair/debug/limbo/login_version_1/last.log",
                            "kind": "log",
                            "excerpt": "A RenderFlex overflowed by 1.5 pixels on the right.\n" * 40,
                            "role": "Row emit with mainAxisSize max " * 20,
                        }
                    ],
                    "repairShape": {
                        "target": "flex_sizing.py",
                        "action": "ensure Row children receive flex factor " * 30,
                    },
                    "forbidden": [f"forbidden rule {index}" for index in range(12)],
                    "proposedLaw": False,
                }
            ],
        },
    )
    return chain


def test_plan_revise_summary_drops_full_steps() -> None:
    from figma_flutter_agent.dev.opencode.chain_compact import compact_plan_revise_summary

    payload = {
        "steps": [
            {
                "order": 1,
                "lawId": "law-a",
                "targetFiles": ["src/x.py"],
                "expectedChange": "x" * 5000,
            }
        ],
        "notes": "revise me",
    }
    summary = compact_plan_revise_summary(payload)
    assert summary["lawIds"] == ["law-a"]
    assert "targetFiles" not in json.dumps(summary)


def test_plan_compact_chain_drops_repeat_symptom_prose() -> None:
    chain = _bloated_chain()
    full_len = len(chain.compact_json())
    compact = chain.compact_for_step("plan")
    compact_len = len(json.dumps(compact))

    assert compact_len < full_len * 0.5
    serialized = json.dumps(compact)
    assert "relatesToSymptoms" not in serialized
    assert "law-fx-overflow-row-mainaxis-sizing" in serialized
    assert compact["diagnose"]["laws"][0]["evidence"][0]["excerpt"].endswith("...")


def test_plan_user_prompt_has_run_facts_not_full_chain(tmp_path) -> None:
    worktree = tmp_path / "wt"
    mirror = worktree / ".repair" / "debug" / "limbo" / "login_version_1"
    mirror.mkdir(parents=True)
    (mirror / "run_manifest.json").write_text(
        json.dumps({"verdict": "CAPTURE_FAILED", "writeback": "committed"}),
        encoding="utf-8",
    )
    (mirror / "capture.json").write_text(
        json.dumps({"flutterCaptureOk": False, "failure_class": "PATCH_RUNTIME"}),
        encoding="utf-8",
    )

    prompt = build_read_step_user_prompt(
        "plan",
        feature="login_version_1",
        board="forensic",
        worktree=worktree,
        debug_mirror=mirror,
        chain=_bloated_chain(),
    )

    assert "CAPTURE_FAILED" in prompt
    assert "PATCH_RUNTIME" in prompt
    assert "relatesToSymptoms" not in prompt


def test_diagnose_user_prompt_forensic_tails_only(tmp_path) -> None:
    worktree = tmp_path / "wt"
    mirror = worktree / ".repair" / "debug" / "limbo" / "sign_up"
    mirror.mkdir(parents=True)
    (mirror / "dart-errors.json").write_text("[]", encoding="utf-8")
    (mirror / "last.log").write_text("RenderFlex overflow tail", encoding="utf-8")
    (mirror / "screen.dart").write_text("class SignUp {}" * 500, encoding="utf-8")

    chain = ReasoningChain()
    chain.append(
        "recognise",
        {"blocked": False, "symptoms": [{"id": "S1", "description": "overflow"}]},
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

    assert "RenderFlex overflow tail" in prompt
    assert "relatesToSymptoms" not in prompt
    assert "class SignUp" not in prompt


def test_compact_chain_for_step_diagnose_includes_recognise_and_inspect_only() -> None:
    chain = _bloated_chain()
    compact = compact_chain_for_step(chain.steps, "diagnose")
    assert "recognise" in compact
    assert "inspect" in compact
    assert "diagnose" not in compact
