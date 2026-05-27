"""Figma REST API data models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FigmaDocument(BaseModel):
    """Top-level Figma document node."""

    id: str
    name: str
    type: str
    children: list[dict[str, Any]] = Field(default_factory=list)


class FigmaNodesResponse(BaseModel):
    """Response payload for GET /v1/files/:key/nodes."""

    name: str | None = None
    nodes: dict[str, FigmaNodeEntry] = Field(default_factory=dict)
    styles: dict[str, dict[str, Any]] | None = None


class FigmaFileResponse(BaseModel):
    """Response payload for GET /v1/files/:key."""

    name: str | None = None
    document: dict[str, Any] | None = None
    components: dict[str, Any] = Field(default_factory=dict)
    component_sets: dict[str, Any] = Field(default_factory=dict, alias="componentSets")
    styles: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class FigmaNodeEntry(BaseModel):
    """Single node entry returned by the nodes endpoint."""

    document: dict[str, Any] | None = None
    styles: dict[str, dict[str, Any]] | None = None


class FigmaVariablesResponse(BaseModel):
    """Response payload for GET /v1/files/:key/variables/local."""

    meta: dict[str, Any] = Field(default_factory=dict)
    status: int | None = None


class FigmaImagesResponse(BaseModel):
    """Response payload for GET /v1/images/:key."""

    images: dict[str, str | None] = Field(default_factory=dict)
    err: str | None = None


class FigmaStylesResponse(BaseModel):
    """Response payload for GET /v1/files/:key/styles."""

    meta: dict[str, Any] = Field(default_factory=dict)


class FigmaComponentsResponse(BaseModel):
    """Response payload for GET /v1/files/:key/components."""

    meta: dict[str, Any] = Field(default_factory=dict)


class FigmaComponentSetsResponse(BaseModel):
    """Response payload for GET /v1/files/:key/component_sets."""

    meta: dict[str, Any] = Field(default_factory=dict)
