"""Tests for wizard/pipeline startup optimizations."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.figma.url import parse_figma_url
from figma_flutter_agent.parser.boundaries.assets import (
    build_asset_node_index,
    lookup_asset_path_for_node,
)
from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
from figma_flutter_agent.pipeline.dump_prefetch import ScreenDumpPrefetch
from figma_flutter_agent.pipeline.run.stages import run_dump_fetch_parse_phase
from figma_flutter_agent.pipeline_context import PipelineContext
from figma_flutter_agent.stages.parse import parse_figma_frame
from figma_flutter_agent.tools.stale_process_cleanup import (
    cleanup_stale_agent_processes,
    reset_stale_cleanup_session,
)


def test_build_asset_node_index_maps_layer_suffix_and_render_boundary(tmp_path: Path) -> None:
    icons = tmp_path / "assets" / "icons"
    illustrations = tmp_path / "assets" / "illustrations"
    icons.mkdir(parents=True)
    illustrations.mkdir(parents=True)
    (icons / "logo_1_2.svg").write_text("<svg/>", encoding="utf-8")
    (illustrations / "render_boundary_3_4.svg").write_text("<svg/>", encoding="utf-8")

    index = build_asset_node_index(tmp_path)
    assert lookup_asset_path_for_node(index, "1:2") == "assets/icons/logo_1_2.svg"
    assert (
        lookup_asset_path_for_node(index, "3:4") == "assets/illustrations/render_boundary_3_4.svg"
    )


def test_stale_cleanup_runs_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_stale_cleanup_session()
    calls = {"count": 0}

    def _fake_windows() -> int:
        calls["count"] += 1
        return 0

    monkeypatch.setattr(
        "figma_flutter_agent.tools.stale_process_cleanup._cleanup_windows",
        _fake_windows,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.tools.stale_process_cleanup.sys.platform",
        "win32",
    )

    cleanup_stale_agent_processes(log=False)
    cleanup_stale_agent_processes(log=False)
    assert calls["count"] == 1

    cleanup_stale_agent_processes(log=False, force=True)
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_run_dump_fetch_parse_phase_reuses_dump_prefetch(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
    dump_dir = project / ".debug" / "raw"
    dump_dir.mkdir(parents=True)
    dump_path = dump_dir / "screen.json"
    dump_path.write_text(
        json.dumps(
            {
                "id": "1:1",
                "name": "Screen",
                "type": "FRAME",
                "children": [],
            }
        ),
        encoding="utf-8",
    )

    fetch = load_fetch_result_from_dump(dump_path, file_key="abc", node_id="1:1")
    parsed = parse_figma_frame(fetch)
    prefetch = ScreenDumpPrefetch(
        dump_path=dump_path.resolve(),
        fetch_result=fetch,
        parse_result=parsed,
    )
    settings = Settings()
    parsed_url = parse_figma_url("https://www.figma.com/design/abc/S?node-id=1-1")
    ctx = PipelineContext(
        settings=settings,
        project_dir=project,
        parsed=parsed_url,
        dry_run=True,
        verbose=False,
        resolved_sync=True,
        feature_name="screen",
        regenerate_templates=False,
    )
    log = MagicMock()
    parse_fn = MagicMock(side_effect=AssertionError("parse_fn must not run when prefetch is set"))

    await run_dump_fetch_parse_phase(
        ctx,
        log=log,
        parsed=parsed_url,
        settings=settings,
        project_dir=project,
        from_dump=dump_path,
        dry_run=True,
        offline_dump_mode=True,
        pipeline_deps=MagicMock(),
        dev_mode_dump=None,
        dev_mode_css_override=False,
        parse_fn=parse_fn,
        dump_prefetch=prefetch,
    )

    parse_fn.assert_not_called()
    assert ctx.clean_tree is not None
    assert ctx.clean_tree.id == "1:1"
