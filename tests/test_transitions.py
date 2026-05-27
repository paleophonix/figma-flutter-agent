from figma_flutter_agent.parser.transitions import parse_prototype_transition


def test_parse_prototype_transition_maps_easing_and_duration() -> None:
    transition = parse_prototype_transition(
        {
            "type": "DISSOLVE",
            "duration": 0.25,
            "easing": {"type": "EASE_OUT"},
        }
    )

    assert transition is not None
    assert transition.duration_ms == 250
    assert transition.flutter_curve == "Curves.easeOut"
    assert transition.transition_kind == "fade"


def test_parse_prototype_transition_supports_slide_kind() -> None:
    transition = parse_prototype_transition(
        {
            "type": "SLIDE_IN",
            "duration": 0.4,
            "easing": {"type": "EASE_IN_AND_OUT"},
        }
    )

    assert transition is not None
    assert transition.transition_kind == "slide"
    assert transition.flutter_curve == "Curves.easeInOut"


def test_parse_prototype_transition_instant_zero_duration() -> None:
    transition = parse_prototype_transition({"type": "INSTANT"})

    assert transition is not None
    assert transition.transition_kind == "instant"
    assert transition.duration_ms == 0


def test_parse_prototype_transition_smart_maps_to_scale() -> None:
    transition = parse_prototype_transition(
        {
            "type": "SMART_ANIMATE",
            "duration": 0.3,
            "easing": {"type": "GENTLE"},
        }
    )

    assert transition is not None
    assert transition.transition_kind == "scale"
    assert transition.flutter_curve == "Curves.easeOutCubic"
