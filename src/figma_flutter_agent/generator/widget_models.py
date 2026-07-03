"""Reusable cluster widget extraction models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode

ClusterSourceKind = Literal[
    "repetition",
    "annotation",
    "inference",
    "shape",
    "component_family",
]


@dataclass(frozen=True)
class ClusterWidgetSpec:
    """Metadata for a cluster-backed reusable widget."""

    cluster_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode
    param_bundle: object | None = None
    shape_members: tuple[CleanDesignTreeNode, ...] = ()
    source_kind: ClusterSourceKind = "repetition"


@dataclass(frozen=True)
class ClusterWidgetResult:
    """Generated cluster widget files and lookup tables."""

    files: dict[str, str]
    cluster_classes: dict[str, str]
