"""Tests for post-repair regenerate mirror isolation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.dev.opencode.regenerate_mirror import (
    _run_pipeline_in_worktree,
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
    captured: list[list[str]] = []

    async def _fake_exec(*cmd: str, **kwargs: object) -> AsyncMock:
        captured.append(list(cmd))
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
    ):
        outcome = await _run_pipeline_in_worktree(
            worktree,
            request={"project_dir": "/tmp/project", "from_dump": "/tmp/raw.json"},
            state_dir=state_dir,
        )

    assert outcome["passed"] is True
    assert captured
    assert captured[0][:3] == ["poetry", "-P", str(worktree.resolve())]
    assert "figma_flutter_agent.dev.opencode.regenerate_pipeline_child" in captured[0]


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

    async def _fake_pipeline(
        worktree_arg: Path,
        *,
        request: dict[str, object],
        state_dir: Path,
    ) -> dict[str, object]:
        assert worktree_arg == worktree
        assert request["from_dump"]
        return {"passed": True, "written_files": ["lib/generated/login_layout.dart"], "run_id": "r2"}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror._run_pipeline_in_worktree",
        _fake_pipeline,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror.screen_root",
        lambda _project_dir, _feature: feature_root,
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
