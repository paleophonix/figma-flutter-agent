"""Legacy agent-repo ``logs/`` debug tree cleanup."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.agent_logs import purge_legacy_agent_debug_log_dirs


def test_purge_legacy_agent_debug_log_dirs_removes_mirror_shards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_root = tmp_path / "agent"
    logs = agent_root / "logs"
    for name in ("dart", "reports", "semantics", "figma-debug"):
        (logs / name / "artifact.json").parent.mkdir(parents=True)
        (logs / name / "artifact.json").write_text("{}", encoding="utf-8")
    (logs / "figma_flutter_agent.log").write_text("telemetry\n", encoding="utf-8")

    monkeypatch.setattr(
        "figma_flutter_agent.debug.agent_logs.agent_repo_root",
        lambda: agent_root,
    )

    removed = purge_legacy_agent_debug_log_dirs()
    assert removed == 4
    assert not (logs / "dart").exists()
    assert not (logs / "reports").exists()
    assert not (logs / "semantics").exists()
    assert not (logs / "figma-debug").exists()
    assert (logs / "figma_flutter_agent.log").is_file()
