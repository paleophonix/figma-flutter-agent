"""Auto-generated per-family case indexes under ``corpus/index/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from figma_flutter_agent.defects.loader import load_corpus
from figma_flutter_agent.defects.models import CaseDocument, LoadedCorpus, OccurrenceEntry
from figma_flutter_agent.defects.paths import cases_dir, corpus_root, index_dir

_INDEX_VERSION = 1
_SUMMARY_MAX_LEN = 280
_yaml = YAML()
_yaml.default_flow_style = False


@dataclass(frozen=True)
class IndexCaseRef:
    """One occurrence row in a family index file."""

    case_id: str
    case_file: str
    title: str
    project: str
    feature: str
    occurrence_id: str
    status: str
    observed_at: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        """Convert to YAML-serializable dict."""
        return {
            "case_id": self.case_id,
            "case_file": self.case_file,
            "title": self.title,
            "project": self.project,
            "feature": self.feature,
            "occurrence_id": self.occurrence_id,
            "status": self.status,
            "observed_at": self.observed_at,
            "summary": self.summary,
        }


def _collapse_summary(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SUMMARY_MAX_LEN:
        return collapsed
    return collapsed[: _SUMMARY_MAX_LEN - 3].rstrip() + "..."


def _case_file_rel(case_path: str) -> str:
    normalized = Path(case_path.replace("\\", "/"))
    try:
        return normalized.relative_to(corpus_root()).as_posix()
    except ValueError:
        pass
    text = normalized.as_posix()
    if text.startswith("corpus/"):
        return text[len("corpus/") :]
    if text.startswith("cases/"):
        return text
    return f"cases/{normalized.name}"


def _index_entry(
    case_path: str,
    case_doc: CaseDocument,
    occurrence: OccurrenceEntry,
) -> IndexCaseRef:
    meta = case_doc.case
    return IndexCaseRef(
        case_id=meta.id,
        case_file=_case_file_rel(case_path),
        title=meta.title,
        project=meta.project,
        feature=meta.feature,
        occurrence_id=occurrence.id,
        status=occurrence.status.value,
        observed_at=meta.observed_at.isoformat(),
        summary=_collapse_summary(meta.summary),
    )


def build_family_indexes(corpus: LoadedCorpus) -> dict[str, list[IndexCaseRef]]:
    """Group index rows by ``family_id`` from all case occurrences."""
    grouped: dict[str, list[IndexCaseRef]] = {}
    for case_path, case_doc in corpus.cases:
        for occurrence in case_doc.occurrences:
            grouped.setdefault(occurrence.family_id, []).append(
                _index_entry(case_path, case_doc, occurrence),
            )
    for family_id, entries in grouped.items():
        entries.sort(
            key=lambda item: (item.observed_at, item.case_id, item.occurrence_id),
            reverse=True,
        )
        grouped[family_id] = entries
    return grouped


def _index_payload(family_id: str, entries: list[IndexCaseRef]) -> dict[str, Any]:
    return {
        "version": _INDEX_VERSION,
        "family_id": family_id,
        "generated": True,
        "cases": [entry.to_dict() for entry in entries],
    }


def _serialize_index(payload: dict[str, Any]) -> str:
    from io import StringIO

    buffer = StringIO()
    _yaml.dump(payload, buffer)
    return buffer.getvalue()


def write_family_indexes(
    corpus: LoadedCorpus | None = None,
    *,
    index_directory: Path | None = None,
) -> list[Path]:
    """Write ``corpus/index/<family_id>.yaml`` files from committed cases."""
    loaded = corpus or load_corpus()
    grouped = build_family_indexes(loaded)
    target = index_directory or index_dir()
    target.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    expected_names = {f"{family_id}.yaml" for family_id in grouped}

    for family_id, entries in sorted(grouped.items()):
        path = target / f"{family_id}.yaml"
        content = _serialize_index(_index_payload(family_id, entries))
        path.write_text(content, encoding="utf-8")
        written.append(path)

    for stale in target.glob("*.yaml"):
        if stale.name not in expected_names:
            stale.unlink()

    return written


def check_family_indexes(
    corpus: LoadedCorpus | None = None,
    *,
    index_directory: Path | None = None,
) -> list[str]:
    """Return human-readable errors when on-disk indexes differ from cases."""
    loaded = corpus or load_corpus()
    grouped = build_family_indexes(loaded)
    target = index_directory or index_dir()
    errors: list[str] = []

    expected_names = {f"{family_id}.yaml" for family_id in grouped}
    if target.is_dir():
        for stale in target.glob("*.yaml"):
            if stale.name not in expected_names:
                errors.append(f"stale index file: {stale.as_posix()}")
    else:
        if grouped:
            errors.append(f"missing index directory: {target.as_posix()}")

    for family_id, entries in sorted(grouped.items()):
        path = target / f"{family_id}.yaml"
        expected = _serialize_index(_index_payload(family_id, entries))
        if not path.is_file():
            errors.append(f"missing index file: {path.as_posix()}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(f"index out of date: {path.as_posix()}")

    return errors
