"""Tests for post-repair regenerate mirror isolation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.dev.opencode.regenerate_mirror import (
    _run_pipeline_in_worktree,
    resolve_regenerate_debug_screen_root,
    resolve_regenerate_pipeline_child_script,
    resolve_regenerate_proof_mode,
    run_regenerate_after_compiler_repair,
)
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


@pytest.mark.asyncio
async def test_run_pipeline_in_worktree_uses_poetry_project_flag(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    orchestrator = tmp_path / "orchestrator"
    orchestrator.mkdir()
    captured: list[list[str]] = []
    captured_env: list[dict[str, str]] = []

    async def _fake_exec(*cmd: str, **kwargs: object) -> AsyncMock:
        captured.append(list(cmd))
        env = kwargs.get("env")
        if isinstance(env, dict):
            captured_env.append(env)
        result_path = Path(cmd[-1])
        result_path.write_text(
            json.dumps({"passed": True, "written_files": [], "run_id": "r1"}),
            encoding="utf-8",
        )
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b""))
        proc.returncode = 0
        return proc

    with (
        patch(
            "figma_flutter_agent.dev.opencode.regenerate_mirror.ensure_worktree_poetry_env",
        ),
        patch("asyncio.create_subprocess_exec", side_effect=_fake_exec),
        patch(
            "figma_flutter_agent.dev.opencode.regenerate_mirror.emit_repair_progress",
        ),
        patch(
            "figma_flutter_agent.dev.opencode.regenerate_mirror._regenerate_heartbeat",
            new=AsyncMock(),
        ),
    ):
        outcome = await _run_pipeline_in_worktree(
            worktree,
            request={"project_dir": "/tmp/project", "from_dump": "/tmp/raw.json"},
            state_dir=state_dir,
            timeout_sec=900,
            orchestrator_root=orchestrator,
        )

    assert outcome["passed"] is True
    assert captured
    assert captured[0][:3] == ["poetry", "-P", str(worktree.resolve())]
    child_script = resolve_regenerate_pipeline_child_script()
    assert captured[0][5] == str(child_script)
    assert captured_env


@pytest.mark.asyncio
async def test_run_pipeline_in_worktree_times_out(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    orchestrator = tmp_path / "orchestrator"
    orchestrator.mkdir()

    class _SlowProc:
        returncode: int | None = None

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(5)
            return b"", b""

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            self.returncode = -9
            return -9

    with (
        patch(
            "figma_flutter_agent.dev.opencode.regenerate_mirror.ensure_worktree_poetry_env",
        ),
        patch("asyncio.create_subprocess_exec", return_value=_SlowProc()),
        patch(
            "figma_flutter_agent.dev.opencode.regenerate_mirror.emit_repair_progress",
        ),
    ):
        outcome = await _run_pipeline_in_worktree(
            worktree,
            request={"project_dir": "/tmp/project", "from_dump": "/tmp/raw.json"},
            state_dir=state_dir,
            timeout_sec=1,
            orchestrator_root=orchestrator,
        )

    assert outcome["passed"] is False
    assert outcome.get("reason_code") == "REGENERATE_TIMEOUT"


def test_resolve_regenerate_pipeline_child_script_uses_orchestrator_checkout() -> None:
    script = resolve_regenerate_pipeline_child_script()
    assert script.name == "regenerate_pipeline_child.py"
    assert script.is_file()


@pytest.mark.asyncio
async def test_regenerate_after_compiler_repair_refreshes_mirror_from_worktree_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    state_dir = worktree / ".repair" / "state"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    (debug_mirror / "raw.json").write_text("{}", encoding="utf-8")

    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: limbo\n", encoding="utf-8")
    sandbox_root = worktree / ".debug" / "flutter_project" / "login"
    sandbox_root.mkdir(parents=True)
    (sandbox_root / "screen.dart").write_text("// generated\n", encoding="utf-8")

    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )

    async def _fake_pipeline(
        worktree_arg: Path,
        *,
        request: dict[str, object],
        state_dir: Path,
        timeout_sec: int,
        orchestrator_root: Path,
    ) -> dict[str, object]:
        assert worktree_arg == worktree
        assert request["from_dump"]
        sandbox = str(request["project_dir"])
        assert "candidate/flutter_project" in sandbox.replace("\\", "/")
        assert sandbox.replace("\\", "/") != project_dir.resolve().as_posix()
        assert request.get("pipeline_invocation") == "repair_regenerate"
        return {"passed": True, "written_files": ["lib/generated/login_layout.dart"], "run_id": "r2"}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror._run_pipeline_in_worktree",
        _fake_pipeline,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror.ensure_flutter_project_sandbox",
        lambda workspace, source: worktree / ".repair" / "candidate" / "flutter_project",
    )

    from figma_flutter_agent.config import load_settings

    result = await run_regenerate_after_compiler_repair(
        workspace=workspace,
        settings=load_settings(),
        project_dir=project_dir,
        feature="login",
    )

    assert result.passed
    assert (debug_mirror / "screen.dart").is_file()
    assert result.payload.get("worktree_isolated") is True
    assert "flutter_project/login" in str(result.payload.get("mirror_source_dir", "")).replace(
        "\\", "/"
    )
    assert "candidate/flutter_project" in str(result.payload.get("sandbox_project_dir", "")).replace(
        "\\", "/"
    )


def test_resolve_regenerate_debug_screen_root_prefers_worktree_sandbox_label(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    sandbox_dir = worktree / ".repair" / "candidate" / "flutter_project"
    sandbox_dir.mkdir(parents=True)
    fresh = worktree / ".debug" / "flutter_project" / "login_version_1"
    fresh.mkdir(parents=True)
    (fresh / "processed.json").write_text("{}", encoding="utf-8")

    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=worktree / ".repair" / "state",
        debug_mirror=worktree / ".repair" / "debug" / "limbo" / "login_version_1",
        manifest_path=worktree / ".repair" / "manifest.json",
    )

    resolved = resolve_regenerate_debug_screen_root(
        workspace=workspace,
        source_project_dir=project_dir,
        sandbox_project_dir=sandbox_dir,
        feature="login_version_1",
    )
    assert resolved == fresh


@pytest.mark.asyncio
async def test_regenerate_mirror_refresh_failure_returns_result_not_raise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    state_dir = worktree / ".repair" / "state"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    (debug_mirror / "raw.json").write_text("{}", encoding="utf-8")

    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: limbo\n", encoding="utf-8")

    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )

    async def _fake_pipeline(
        worktree_arg: Path,
        *,
        request: dict[str, object],
        state_dir: Path,
        timeout_sec: int,
        orchestrator_root: Path,
    ) -> dict[str, object]:
        return {"passed": True, "written_files": [], "run_id": "r-mirror-fail"}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror._run_pipeline_in_worktree",
        _fake_pipeline,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror.ensure_flutter_project_sandbox",
        lambda workspace, source: worktree / ".repair" / "candidate" / "flutter_project",
    )

    from figma_flutter_agent.config import load_settings

    result = await run_regenerate_after_compiler_repair(
        workspace=workspace,
        settings=load_settings(),
        project_dir=project_dir,
        feature="login",
    )
    assert result.passed is False
    assert result.payload.get("reason_code") == "MIRROR_REFRESH_FAILED"


def test_resolve_regenerate_proof_mode_raw_replay_for_parser_targets() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/parser/tree.py"],
                "tests": ["tests/test_parser.py"],
            }
        ]
    }
    assert resolve_regenerate_proof_mode(plan) == "raw_replay"


def test_resolve_regenerate_proof_mode_cached_ir_for_emit_targets() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                ],
                "tests": ["tests/test_flex.py"],
            }
        ]
    }
    assert resolve_regenerate_proof_mode(plan) == "cached_ir"


@pytest.mark.asyncio
async def test_regenerate_parser_plan_disables_cached_ir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    state_dir = worktree / ".repair" / "state"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    (debug_mirror / "raw.json").write_text("{}", encoding="utf-8")
    (debug_mirror / "llm_validated.json").write_text("{}", encoding="utf-8")

    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: limbo\n", encoding="utf-8")
    feature_root = tmp_path / "source_mirror"
    feature_root.mkdir(parents=True)
    (feature_root / "screen.dart").write_text("// generated\n", encoding="utf-8")

    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )
    captured_request: dict[str, object] = {}

    async def _fake_pipeline(
        worktree_arg: Path,
        *,
        request: dict[str, object],
        state_dir: Path,
        timeout_sec: int,
        orchestrator_root: Path,
    ) -> dict[str, object]:
        captured_request.update(request)
        return {"passed": True, "written_files": [], "run_id": "r3"}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror._run_pipeline_in_worktree",
        _fake_pipeline,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror.ensure_flutter_project_sandbox",
        lambda workspace, source: worktree / ".repair" / "candidate" / "flutter_project",
    )
    worktree_sandbox_debug = (
        worktree / ".debug" / "flutter_project" / "login"
    )
    worktree_sandbox_debug.mkdir(parents=True)
    (worktree_sandbox_debug / "screen.dart").write_text("// generated\n", encoding="utf-8")

    from figma_flutter_agent.config import load_settings

    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/parser/tree.py"],
                "tests": ["tests/test_parser.py"],
            }
        ]
    }
    result = await run_regenerate_after_compiler_repair(
        workspace=workspace,
        settings=load_settings(),
        project_dir=project_dir,
        feature="login",
        plan_payload=plan,
    )
    assert result.passed
    assert captured_request.get("from_ir") is False
    assert result.payload.get("proof_mode") == "raw_replay"


def test_resolve_regenerate_proof_mode_raw_replay_from_diagnose_layer() -> None:
    diagnose = {"laws": [{"lawId": "ParseTreeLaw", "layer": "parse"}]}
    assert resolve_regenerate_proof_mode(None, diagnose) == "raw_replay"


def test_refresh_debug_mirror_rejects_run_id_mismatch(tmp_path: Path) -> None:
    from figma_flutter_agent.debug.paths import RUN_META_JSON
    from figma_flutter_agent.dev.opencode.regenerate_mirror import refresh_debug_mirror
    from figma_flutter_agent.errors import FigmaFlutterError

    worktree = tmp_path / "wt"
    worktree.mkdir()
    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    sandbox_dir = worktree / ".repair" / "candidate" / "flutter_project"
    sandbox_dir.mkdir(parents=True)
    fresh = worktree / ".debug" / "flutter_project" / "login"
    fresh.mkdir(parents=True)
    (fresh / RUN_META_JSON).write_text(
        '{"pipeline_run_id":"meta-run","committed_build_run_id":"meta-run"}',
        encoding="utf-8",
    )
    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=worktree / ".repair" / "state",
        debug_mirror=worktree / ".repair" / "debug" / "limbo" / "login",
        manifest_path=worktree / ".repair" / "manifest.json",
    )
    with pytest.raises(FigmaFlutterError, match="RUN_ID_MISMATCH"):
        refresh_debug_mirror(
            workspace=workspace,
            source_project_dir=project_dir,
            sandbox_project_dir=sandbox_dir,
            feature="login",
            regen_run_id="subprocess-run",
        )


def test_validate_mirror_run_id_skips_when_meta_absent(tmp_path: Path) -> None:
    from figma_flutter_agent.dev.opencode.regenerate_mirror import refresh_debug_mirror

    worktree = tmp_path / "wt"
    worktree.mkdir()
    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    sandbox_dir = worktree / ".repair" / "candidate" / "flutter_project"
    sandbox_dir.mkdir(parents=True)
    fresh = worktree / ".debug" / "flutter_project" / "login"
    fresh.mkdir(parents=True)
    (fresh / "screen.dart").write_text("// ok\n", encoding="utf-8")
    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=worktree / ".repair" / "state",
        debug_mirror=worktree / ".repair" / "debug" / "limbo" / "login",
        manifest_path=worktree / ".repair" / "manifest.json",
    )
    result = refresh_debug_mirror(
        workspace=workspace,
        source_project_dir=project_dir,
        sandbox_project_dir=sandbox_dir,
        feature="login",
        regen_run_id="subprocess-run",
    )
    assert result.mirror_dir.is_dir()
