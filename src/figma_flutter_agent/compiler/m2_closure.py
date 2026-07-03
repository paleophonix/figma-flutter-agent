"""Typed M2 closure record parser (authority gate)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

M2_CLOSURE_RECORD_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/m2-closure-record.md"
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TABLE_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*([^|]*)\|",
    re.MULTILINE,
)
_UNSET_MARKERS = frozenset({"_(unset)_", "_(unset)_ —", ""})


@dataclass(frozen=True, slots=True)
class M2ClosureRecord:
    """Parsed M2 closure record from generated markdown."""

    status: Literal["PENDING", "CLOSED"]
    final_commit: str | None
    ci_green: bool
    acceptance_report: str | None
    signed_off_by: str | None
    signed_off_at: datetime | None


def _clean_cell(raw: str) -> str:
    value = raw.strip()
    if value.startswith("[") and "](" in value:
        value = value.split("](", maxsplit=1)[0].removeprefix("[")
    value = value.strip("`").strip()
    return value


def _parse_status(text: str) -> Literal["PENDING", "CLOSED"]:
    if re.search(r"\*\*Status:\*\*\s*`?CLOSED`?", text, re.IGNORECASE):
        return "CLOSED"
    return "PENDING"


def _parse_signed_off_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def load_m2_closure_record(*, repo_root: Path | None = None) -> M2ClosureRecord | None:
    """Load closure record from canonical markdown path."""
    root = repo_root or Path(__file__).resolve().parents[3]
    path = root / M2_CLOSURE_RECORD_REL
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for match in _TABLE_ROW_RE.finditer(text):
        key, raw_value = match.group(1), match.group(2)
        fields[key] = _clean_cell(raw_value)
    ci_raw = fields.get("CI_GREEN", "").strip().lower()
    ci_green = ci_raw in {"true", "yes", "1"}
    return M2ClosureRecord(
        status=_parse_status(text),
        final_commit=fields.get("M2_FINAL_COMMIT") or None,
        ci_green=ci_green,
        acceptance_report=fields.get("ACCEPTANCE_REPORT") or None,
        signed_off_by=fields.get("SIGNED_OFF_BY") or None,
        signed_off_at=_parse_signed_off_at(fields.get("SIGNED_OFF_AT")),
    )


def m2_closure_record_is_valid(record: M2ClosureRecord | None) -> bool:
    """Return True only when all required closure fields are populated."""
    if record is None or record.status != "CLOSED":
        return False
    commit = (record.final_commit or "").strip().lower()
    if not _SHA_RE.fullmatch(commit):
        return False
    if not record.ci_green:
        return False
    report = (record.acceptance_report or "").strip()
    if not report or report in _UNSET_MARKERS or report.startswith("_("):
        return False
    signer = (record.signed_off_by or "").strip()
    if not signer or signer in _UNSET_MARKERS or signer.startswith("_("):
        return False
    return record.signed_off_at is not None
