"""Cross-validation rules for the defect corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from figma_flutter_agent.defects.loader import load_corpus
from figma_flutter_agent.defects.models import LoadedCorpus, OccurrenceEntry
from figma_flutter_agent.defects.paths import families_path

_FAMILY_ID_RE = re.compile(r"^[a-z][a-z0-9_]+$")
_FORBIDDEN_PATH_PREFIXES = ("C:", "c:", "/", "\\\\")
_SECRET_MARKERS = ("FIGMA_ACCESS_TOKEN", "Bearer ", "sk-", "phc_")


@dataclass(frozen=True)
class ValidationError:
    """One corpus validation failure."""

    file_path: str
    field_path: str
    message: str

    def format(self) -> str:
        """Render as ``file:field: message``."""
        return f"{self.file_path}:{self.field_path}: {self.message}"


def validate_corpus(corpus: LoadedCorpus | None = None) -> list[ValidationError]:
    """Validate families and all case documents.

    Args:
        corpus: Optional pre-loaded corpus; loads from disk when omitted.

    Returns:
        Sorted list of validation errors (empty when valid).
    """
    loaded = corpus or load_corpus()
    errors: list[ValidationError] = []
    families_file = families_path().as_posix()
    family_ids: set[str] = set()
    case_ids: set[str] = set()

    for index, family in enumerate(loaded.families.families):
        prefix = f"families[{index}]"
        if family.id in family_ids:
            errors.append(
                ValidationError(families_file, f"{prefix}.id", f"duplicate family id {family.id!r}"),
            )
        family_ids.add(family.id)
        if not _FAMILY_ID_RE.match(family.id):
            errors.append(
                ValidationError(
                    families_file,
                    f"{prefix}.id",
                    f"family id {family.id!r} does not match {_FAMILY_ID_RE.pattern}",
                ),
            )
        if not family.law_ids or any(not law.strip() for law in family.law_ids):
            errors.append(
                ValidationError(families_file, f"{prefix}.law_ids", "law_ids must be non-empty"),
            )

    for file_path, case_doc in loaded.cases:
        case = case_doc.case
        case_prefix = "case"
        if case.id in case_ids:
            errors.append(
                ValidationError(file_path, f"{case_prefix}.id", f"duplicate case id {case.id!r}"),
            )
        case_ids.add(case.id)

        occurrence_ids: set[str] = set()
        for occ_index, occurrence in enumerate(case_doc.occurrences):
            occ_prefix = f"case.occurrences[{occ_index}]"
            errors.extend(_validate_occurrence(file_path, occ_prefix, occurrence, family_ids))

            if occurrence.id in occurrence_ids:
                errors.append(
                    ValidationError(
                        file_path,
                        f"{occ_prefix}.id",
                        f"duplicate occurrence id {occurrence.id!r}",
                    ),
                )
            occurrence_ids.add(occurrence.id)

    return sorted(errors, key=lambda item: (item.file_path, item.field_path, item.message))


def _validate_occurrence(
    file_path: str,
    prefix: str,
    occurrence: OccurrenceEntry,
    family_ids: set[str],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if occurrence.family_id not in family_ids:
        errors.append(
            ValidationError(
                file_path,
                f"{prefix}.family_id",
                f"unknown family {occurrence.family_id!r}",
            ),
        )
    if occurrence.family_id == "UNCLASSIFIED":
        errors.append(
            ValidationError(
                file_path,
                f"{prefix}.family_id",
                "committed case cannot use UNCLASSIFIED",
            ),
        )
    if not occurrence.law_id.strip():
        errors.append(
            ValidationError(file_path, f"{prefix}.law_id", "law_id must be non-empty"),
        )

    errors.extend(_validate_origin_requirements(file_path, prefix, occurrence))
    errors.extend(_validate_paths(file_path, prefix, occurrence))
    return errors


def _validate_origin_requirements(
    file_path: str,
    prefix: str,
    occurrence: OccurrenceEntry,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    origin = occurrence.origin.value

    if origin == "COMPILER":
        has_boundary = bool(occurrence.authority_boundary or occurrence.loss_boundary)
        has_law_evidence = any(item.kind in {"source_code", "test"} for item in occurrence.evidence)
        if not has_boundary and not has_law_evidence:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.origin",
                    "COMPILER requires authority_boundary, loss_boundary, or law evidence",
                ),
            )

    if origin == "SOURCE":
        if not any(item.kind == "debug_artifact" for item in occurrence.evidence):
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.origin",
                    "SOURCE requires at least one debug_artifact evidence item",
                ),
            )

    if origin == "AMBIGUOUS":
        if not occurrence.missing_evidence:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.missing_evidence",
                    "AMBIGUOUS requires missing_evidence entries",
                ),
            )

    if occurrence.status.value == "FIXED":
        if occurrence.repair is None:
            errors.append(
                ValidationError(file_path, f"{prefix}.repair", "FIXED requires repair block"),
            )
        else:
            if not occurrence.repair.changed_files:
                errors.append(
                    ValidationError(
                        file_path,
                        f"{prefix}.repair.changed_files",
                        "FIXED requires changed_files",
                    ),
                )
            if not occurrence.repair.regression_tests:
                errors.append(
                    ValidationError(
                        file_path,
                        f"{prefix}.repair.regression_tests",
                        "FIXED requires regression_tests",
                    ),
                )
            if not occurrence.repair.verification:
                errors.append(
                    ValidationError(
                        file_path,
                        f"{prefix}.repair.verification",
                        "FIXED requires verification commands",
                    ),
                )

    if occurrence.status.value == "DEFERRED_BY_POLICY" and not occurrence.defer_reason:
        errors.append(
            ValidationError(
                file_path,
                f"{prefix}.defer_reason",
                "DEFERRED_BY_POLICY requires defer_reason",
            ),
        )

    return errors


def _validate_paths(
    file_path: str,
    prefix: str,
    occurrence: OccurrenceEntry,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    paths_to_check: list[tuple[str, str]] = [
        (f"{prefix}.owner.module", occurrence.owner.module),
    ]
    for evidence_index, item in enumerate(occurrence.evidence):
        paths_to_check.append((f"{prefix}.evidence[{evidence_index}].path", item.path))
    if occurrence.repair is not None:
        for file_index, changed in enumerate(occurrence.repair.changed_files):
            paths_to_check.append((f"{prefix}.repair.changed_files[{file_index}]", changed))

    for field_path, value in paths_to_check:
        if not value.strip():
            errors.append(ValidationError(file_path, field_path, "path must be non-empty"))
            continue
        if any(value.startswith(prefix) for prefix in _FORBIDDEN_PATH_PREFIXES):
            errors.append(ValidationError(file_path, field_path, "absolute paths are forbidden"))
        if "\\" in value:
            errors.append(ValidationError(file_path, field_path, "use repository-relative posix paths"))
        try:
            PurePosixPath(value)
        except ValueError:
            errors.append(ValidationError(file_path, field_path, f"invalid path {value!r}"))
        if any(marker in value for marker in _SECRET_MARKERS):
            errors.append(ValidationError(file_path, field_path, "path must not contain secrets"))

    return errors
