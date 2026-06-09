"""Shared schema primitive types."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict

ScrollAxis = Literal["none", "vertical", "horizontal", "both"]
HorizontalConstraint = Literal["LEFT", "RIGHT", "CENTER", "LEFT_RIGHT", "SCALE"]
VerticalConstraint = Literal["TOP", "BOTTOM", "CENTER", "TOP_BOTTOM", "SCALE"]

IMMUTABLE_TREE_CONFIG = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)


class NodeType(StrEnum):
    """Semantic node types for the clean design tree."""

    COLUMN = "COLUMN"
    ROW = "ROW"
    WRAP = "WRAP"
    STACK = "STACK"
    GRID = "GRID"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VECTOR = "VECTOR"
    INPUT = "INPUT"
    BUTTON = "BUTTON"
    CHECKBOX = "CHECKBOX"
    SWITCH = "SWITCH"
    RADIO = "RADIO"
    RADIO_GROUP = "RADIO_GROUP"
    DROPDOWN = "DROPDOWN"
    DIALOG = "DIALOG"
    SLIDER = "SLIDER"
    CAROUSEL = "CAROUSEL"
    TABS = "TABS"
    BOTTOM_NAV = "BOTTOM_NAV"
    CARD = "CARD"
    CONTAINER = "CONTAINER"


class SizingMode(StrEnum):
    """Sizing behavior for a node."""

    FIXED = "FIXED"
    HUG = "HUG"
    FILL = "FILL"
