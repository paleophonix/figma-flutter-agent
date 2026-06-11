"""Registry of all semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors.actions import ACTION_DETECTORS
from figma_flutter_agent.parser.semantics.detectors.controls import CONTROL_DETECTORS
from figma_flutter_agent.parser.semantics.detectors.display import DISPLAY_DETECTORS
from figma_flutter_agent.parser.semantics.detectors.inputs import INPUT_DETECTORS
from figma_flutter_agent.parser.semantics.detectors.navigation import NAVIGATION_DETECTORS
from figma_flutter_agent.parser.semantics.detectors.overlays import OVERLAY_DETECTORS
from figma_flutter_agent.parser.semantics.models import Detector
from figma_flutter_agent.schemas import WidgetIrKind

_ALL_DETECTORS: tuple[Detector, ...] = (
    *INPUT_DETECTORS,
    *ACTION_DETECTORS,
    *CONTROL_DETECTORS,
    *NAVIGATION_DETECTORS,
    *DISPLAY_DETECTORS,
    *OVERLAY_DETECTORS,
)

DETECTORS: dict[WidgetIrKind, Detector] = {detector.kind: detector for detector in _ALL_DETECTORS}
