"""Reusable cluster widget extraction models."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True)
class ClusterWidgetSpec:
    """Metadata for a cluster-backed reusable widget."""

    cluster_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode
    param_bundle: object | None = None
    shape_members: tuple[CleanDesignTreeNode, ...] = ()


@dataclass(frozen=True)
class ClusterWidgetResult:
    """Generated cluster widget files and lookup tables."""

    files: dict[str, str]
    cluster_classes: dict[str, str]
