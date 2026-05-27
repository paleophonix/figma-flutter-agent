"""Map Figma prototype transitions to Flutter navigation metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_FLUTTER_CURVES: dict[str, str] = {
    "EASE_IN": "Curves.easeIn",
    "EASE_OUT": "Curves.easeOut",
    "EASE_IN_AND_OUT": "Curves.easeInOut",
    "LINEAR": "Curves.linear",
    "EASE_IN_BACK": "Curves.easeInBack",
    "EASE_OUT_BACK": "Curves.easeOutBack",
    "EASE_IN_AND_OUT_BACK": "Curves.easeInOutBack",
    "GENTLE": "Curves.easeOutCubic",
    "QUICK": "Curves.fastOutSlowIn",
    "BOUNCY": "Curves.elasticOut",
    "SLOW": "Curves.slowMiddle",
}


@dataclass(frozen=True)
class PrototypeTransition:
    """Normalized prototype transition metadata for generated Dart."""

    type: str
    duration_ms: int
    easing: str
    flutter_curve: str
    transition_kind: str


def _resolve_easing(raw_easing: dict[str, Any] | str | None) -> str:
    if isinstance(raw_easing, dict):
        easing_type = raw_easing.get("type")
        if isinstance(easing_type, str):
            return easing_type
        return "EASE_IN_AND_OUT"
    if isinstance(raw_easing, str):
        return raw_easing
    return "EASE_IN_AND_OUT"


def _transition_kind(raw_type: str | None) -> str:
    normalized = (raw_type or "DISSOLVE").upper()
    if normalized in {"DISSOLVE", "FADE"}:
        return "fade"
    if normalized in {"SLIDE_IN", "PUSH", "MOVE_IN", "SLIDE_OUT", "MOVE_OUT"}:
        return "slide"
    if normalized in {"SMART_ANIMATE", "SMART"}:
        return "scale"
    if normalized == "INSTANT":
        return "instant"
    return "fade"


def parse_prototype_transition(raw_transition: dict[str, Any] | None) -> PrototypeTransition | None:
    """Parse a Figma action transition payload into Flutter-ready metadata."""
    if not raw_transition:
        return None

    raw_type = raw_transition.get("type")
    if not isinstance(raw_type, str):
        return None

    duration_seconds = raw_transition.get("duration")
    duration_ms = 300
    if isinstance(duration_seconds, (int, float)):
        duration_ms = max(int(float(duration_seconds) * 1000), 0)

    easing = _resolve_easing(raw_transition.get("easing"))
    flutter_curve = _FLUTTER_CURVES.get(easing, "Curves.easeInOut")
    transition_kind = _transition_kind(raw_type)

    if transition_kind == "instant":
        duration_ms = 0

    return PrototypeTransition(
        type=raw_type.upper(),
        duration_ms=duration_ms,
        easing=easing,
        flutter_curve=flutter_curve,
        transition_kind=transition_kind,
    )
