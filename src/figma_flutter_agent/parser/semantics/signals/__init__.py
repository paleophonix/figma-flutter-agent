"""Signal collectors for semantic classification tiers."""

from figma_flutter_agent.parser.semantics.signals.anatomy import collect_anatomy_signals
from figma_flutter_agent.parser.semantics.signals.geometry import collect_geometry_signals
from figma_flutter_agent.parser.semantics.signals.properties import collect_property_signals

__all__ = [
    "collect_anatomy_signals",
    "collect_geometry_signals",
    "collect_property_signals",
]
