"""Cross-validation rules for the defect corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from figma_flutter_agent.defects.loader import load_case, load_families
from figma_flutter_agent.defects.models import (
    CaseDocument,
    FamilyEntry,
    LoadedCorpus,
    OccurrenceEntry,
)
from figma_flutter_agent.defects.paths import cases_dir, families_path

_FAMILY_ID_RE = re.compile(r"^[a-z][a-z0-9_]+$")
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


def _load_corpus_errors(
    *,
    families_file: Path | None = None,
    cases_directory: Path | None = None,
) -> tuple[LoadedCorpus | None, list[ValidationError]]:
    errors: list[ValidationError] = []
    families_path_resolved = families_file or families_path()
    families_file_posix = families_path_resolved.as_posix()

    try:
        families = load_families(families_file)
    except FileNotFoundError as exc:
        errors.append(ValidationError(families_file_posix, "", str(exc)))
        return None, errors
    except PermissionError as exc:
        errors.append(ValidationError(families_file_posix, "", str(exc)))
        return None, errors
    except ValueError as exc:
        for line in str(exc).split("; "):
            if line.strip():
                errors.append(ValidationError(families_file_posix, "", line.strip()))
        return None, errors

    case_root = cases_directory or cases_dir()
    cases: list[tuple[str, CaseDocument]] = []
    if case_root.is_dir():
        for case_path in sorted(case_root.glob("*.yaml")):
            case_file = case_path.as_posix()
            try:
                cases.append((case_file, load_case(case_path)))
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                errors.append(ValidationError(case_file, "", str(exc)))

    if errors:
        return None, errors
    return LoadedCorpus(families=families, cases=cases), []


def validate_corpus(corpus: LoadedCorpus | None = None) -> list[ValidationError]:
    """Validate families and all case documents.

    Args:
        corpus: Optional pre-loaded corpus; loads from disk when omitted.

    Returns:
        Sorted list of validation errors (empty when valid).
    """
    if corpus is None:
        loaded, load_errors = _load_corpus_errors()
        if load_errors:
            return sorted(load_errors, key=lambda item: (item.file_path, item.field_path, item.message))
        assert loaded is not None
        loaded_corpus = loaded
    else:
        loaded_corpus = corpus

    errors: list[ValidationError] = []
    families_file = families_path().as_posix()
    family_ids: set[str] = set()
    family_by_id: dict[str, FamilyEntry] = {}
    case_ids: set[str] = set()

    for index, family in enumerate(loaded_corpus.families.families):
        prefix = f"families[{index}]"
        if family.id in family_ids:
            errors.append(
                ValidationError(families_file, f"{prefix}.id", f"duplicate family id {family.id!r}"),
            )
        family_ids.add(family.id)
        family_by_id[family.id] = family
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

    for file_path, case_doc in loaded_corpus.cases:
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
            errors.extend(
                _validate_occurrence(file_path, occ_prefix, occurrence, family_by_id),
            )

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
    family_by_id: dict[str, FamilyEntry],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    family = family_by_id.get(occurrence.family_id)
    if family is None:
        errors.append(
            ValidationError(
                file_path,
                f"{prefix}.family_id",
                f"unknown family {occurrence.family_id!r}",
            ),
        )
    else:
        arrow = occurrence.pipeline_arrow.value
        if arrow not in {item.value for item in family.pipeline_arrows}:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.pipeline_arrow",
                    f"pipeline_arrow {arrow!r} not in family {family.id!r} arrows",
                ),
            )
        if occurrence.law_id not in family.law_ids:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.law_id",
                    f"law_id {occurrence.law_id!r} not in family {family.id!r} law_ids",
                ),
            )
        if occurrence.origin not in family.allowed_origins:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.origin",
                    f"origin {occurrence.origin.value!r} not allowed for family {family.id!r}",
                ),
            )
        if occurrence.stage != family.owning_stage:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.stage",
                    (
                        f"stage {occurrence.stage!r} does not match family owning_stage "
                        f"{family.owning_stage!r}"
                    ),
                ),
            )
        family_owners = {(owner.module, owner.symbol) for owner in family.owners}
        owner_key = (occurrence.owner.module, occurrence.owner.symbol)
        if owner_key not in family_owners:
            errors.append(
                ValidationError(
                    file_path,
                    f"{prefix}.owner",
                    f"owner {owner_key!r} not registered on family {family.id!r}",
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


def _is_forbidden_absolute_path(value: str) -> bool:
    if PurePosixPath(value).is_absolute():
        return True
    if PureWindowsPath(value).is_absolute():
        return True
    return bool(re.match(r"^[A-Za-z]:", value))


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
        if _is_forbidden_absolute_path(value):
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
