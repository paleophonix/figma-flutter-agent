"""Enumerations for the defect corpus schema."""

from __future__ import annotations

from enum import StrEnum


class PipelineArrow(StrEnum):
    """First pipeline arrow where a fact changed or a law applies."""

    A1 = "A1"
    A1B = "A1b"
    A2 = "A2"
    A3 = "A3"
    CP2 = "CP2"
    A4 = "A4"
    NONE = "NONE"


class DefectOrigin(StrEnum):
    """Whether the defect is compiler-side, source-side, or ambiguous."""

    COMPILER = "COMPILER"
    SOURCE = "SOURCE"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


class BlastRadius(StrEnum):
    """Severity blast radius for a defect occurrence."""

    B4_CATASTROPHIC = "B4_CATASTROPHIC"
    B3_BLOCKING = "B3_BLOCKING"
    B2_SILENT_WRONG_BEHAVIOR = "B2_SILENT_WRONG_BEHAVIOR"
    B1_STRUCTURAL_DEGRADATION = "B1_STRUCTURAL_DEGRADATION"
    B0_ADVISORY = "B0_ADVISORY"


class DefectStatus(StrEnum):
    """Lifecycle status of a defect occurrence."""

    OPEN = "OPEN"
    IN_REPAIR = "IN_REPAIR"
    FIXED = "FIXED"
    DEFERRED_BY_POLICY = "DEFERRED_BY_POLICY"
    WONT_FIX = "WONT_FIX"


class Confidence(StrEnum):
    """Confidence in the defect classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContractCategory(StrEnum):
    """How the contract field behaved relative to expectation."""

    PRESERVED = "preserved"
    INFERRED = "inferred"
    LOSSY = "lossy"
    ILLEGAL = "illegal"


class FieldClass(StrEnum):
    """Authority class of a contract field."""

    FACT = "fact"
    INTENT = "intent"
    PROPOSAL = "proposal"
    COMPILER_OWNED = "compiler_owned"
    REPORT_ONLY = "report_only"
