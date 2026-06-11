"""Provenance JSON dump tests."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.provenance import (
    activate_provenance_recorder,
    clear_provenance_recorder,
    provenance_dump_path,
    record_decision,
    write_provenance_dump,
)


def test_write_provenance_dump_includes_decisions_stub(tmp_path: Path) -> None:
    recorder = activate_provenance_recorder(feature_name="demo_screen", project_dir=tmp_path)
    recorder.record_mutation(
        checkpoint="CP0_parse",
        transform="dedup_prune",
        node_id="icon:1",
        field="children",
        old=1,
        new=0,
    )
    record_decision(
        node_id="icon:1",
        kind="ICON",
        confidence=0.95,
        evidence={"signal": "structure"},
    )
    path = write_provenance_dump()
    assert path == provenance_dump_path(tmp_path, "demo_screen")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["decisions"] == [
        {
            "nodeId": "icon:1",
            "kind": "ICON",
            "confidence": 0.95,
            "evidence": {"signal": "structure"},
        },
    ]
    assert payload["mutations"][0]["transform"] == "dedup_prune"
    clear_provenance_recorder()
