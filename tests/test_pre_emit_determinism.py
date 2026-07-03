"""Pre-emit determinism gate (Program 10 P1-b)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.debug.paths import screen_ir_dump_path
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from tests.synthetic.builders import column_tree

_EXCLUDE_KEYS = frozenset({"capturedAt", "captured_at", "pipelineRunId", "pipeline_run_id"})


def _canonical_pre_emit_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):

        def scrub(obj):
            if isinstance(obj, dict):
                return {
                    key: scrub(value)
                    for key, value in sorted(obj.items())
                    if key not in _EXCLUDE_KEYS
                }
            if isinstance(obj, list):
                return [scrub(item) for item in obj]
            return obj

        payload = scrub(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("fixture_name", ["home_a", "home_b"])
def test_pre_emit_double_run_hash_equal(tmp_path: Path, fixture_name: str) -> None:
    project = tmp_path / fixture_name
    project.mkdir()
    tree = column_tree(depth=2 if fixture_name.endswith("b") else 1)
    screen_ir = default_screen_ir(tree)
    write_screen_ir_snapshot(
        stage="pre_emit",
        feature_name="screen",
        screen_ir=screen_ir,
        project_dir=project,
        extra={"fixture": fixture_name},
    )
    path = screen_ir_dump_path(project, "screen", "pre_emit")
    first_hash = _canonical_pre_emit_hash(path)
    write_screen_ir_snapshot(
        stage="pre_emit",
        feature_name="screen",
        screen_ir=screen_ir,
        project_dir=project,
        extra={"fixture": fixture_name},
    )
    second_hash = _canonical_pre_emit_hash(path)
    assert first_hash == second_hash
