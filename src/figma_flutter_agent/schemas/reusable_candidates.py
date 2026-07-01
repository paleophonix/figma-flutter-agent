"""Structured reusable widget candidate schemas for gated inference."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReusableWidgetEvidence(BaseModel):
    """Evidence backing an LLM or static reusable widget candidate."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    similar_nodes: list[str] = Field(default_factory=list, alias="similarNodes")
    shape_similarity: float | None = Field(default=None, alias="shapeSimilarity")
    semantic_role: str | None = Field(default=None, alias="semanticRole")


class ReusableWidgetCandidate(BaseModel):
    """One gated reusable widget extraction candidate."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    widget_name: str = Field(alias="widgetName")
    reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_params: list[str] = Field(default_factory=list, alias="suggestedParams")
    evidence: ReusableWidgetEvidence | None = None


class ReusableWidgetCandidatesResponse(BaseModel):
    """LLM structured output for reusable widget candidate detection."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    candidates: list[ReusableWidgetCandidate] = Field(default_factory=list)


class WidgetEnrichEntry(BaseModel):
    """LLM-suggested naming for one cluster widget."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cluster_id: str = Field(alias="clusterId")
    widget_name: str = Field(alias="widgetName")
    param_renames: dict[str, str] = Field(default_factory=dict, alias="paramRenames")


class WidgetEnrichResponse(BaseModel):
    """LLM structured output for cluster widget naming enrichment."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    entries: list[WidgetEnrichEntry] = Field(default_factory=list)
