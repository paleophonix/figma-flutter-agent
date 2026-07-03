"""Tests for typed M2 closure record validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from figma_flutter_agent.compiler.m2_closure import (
    M2ClosureRecord,
    load_m2_closure_record,
    m2_closure_record_is_valid,
)
from figma_flutter_agent.compiler.m3_policy import (
    is_m2_closure_closed,
    m3_policy_at_pipeline_boundary,
)


def _write_record(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "m2-closure-record.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_m2_closure_rejects_status_only_closed(tmp_path: Path, monkeypatch) -> None:
    record_path = _write_record(
        tmp_path,
        """# M2 closure

**Status:** CLOSED

| Field | Value |
| --- | --- |
| `M2_FINAL_COMMIT` | _(unset)_ |
| `CI_GREEN` | false |
| `ACCEPTANCE_REPORT` | _(unset)_ |
| `SIGNED_OFF_BY` | _(unset)_ |
| `SIGNED_OFF_AT` | _(unset)_ |
""",
    )
    monkeypatch.setattr(
        "figma_flutter_agent.compiler.m2_closure.M2_CLOSURE_RECORD_REL",
        str(record_path.relative_to(tmp_path)),
    )
    root = tmp_path
    record = load_m2_closure_record(repo_root=root)
    assert record is not None
    assert record.status == "CLOSED"
    assert m2_closure_record_is_valid(record) is False
    assert is_m2_closure_closed(repo_root=root) is False


def test_m2_closure_accepts_fully_populated_record(tmp_path: Path, monkeypatch) -> None:
    record_path = _write_record(
        tmp_path,
        """# M2 closure

**Status:** CLOSED

| Field | Value |
| --- | --- |
| `M2_FINAL_COMMIT` | `a1b2c3d4e5f6789012345678901234567890abcd` |
| `CI_GREEN` | true |
| `ACCEPTANCE_REPORT` | [acceptance.md](acceptance.md) |
| `SIGNED_OFF_BY` | `compiler-lead` |
| `SIGNED_OFF_AT` | `2026-07-03` |
""",
    )
    monkeypatch.setattr(
        "figma_flutter_agent.compiler.m2_closure.M2_CLOSURE_RECORD_REL",
        str(record_path.relative_to(tmp_path)),
    )
    root = tmp_path
    record = load_m2_closure_record(repo_root=root)
    assert record is not None
    assert m2_closure_record_is_valid(record) is True
    assert is_m2_closure_closed(repo_root=root) is True


def test_m2_closure_record_dataclass_validation() -> None:
    valid = M2ClosureRecord(
        status="CLOSED",
        final_commit="a1b2c3d4e5f6789012345678901234567890abcd",
        ci_green=True,
        acceptance_report="acceptance.md",
        signed_off_by="lead",
        signed_off_at=datetime(2026, 7, 3),
    )
    assert m2_closure_record_is_valid(valid) is True

    pending = M2ClosureRecord(
        status="PENDING",
        final_commit=None,
        ci_green=False,
        acceptance_report=None,
        signed_off_by=None,
        signed_off_at=None,
    )
    assert m2_closure_record_is_valid(pending) is False


def test_authority_stays_off_when_closure_incomplete(monkeypatch) -> None:
    monkeypatch.delenv("FIGMA_M3_AUTHORITY_ENABLED", raising=False)
    policy = m3_policy_at_pipeline_boundary()
    assert policy.m2_closed is False
    assert policy.authority_enabled is False
