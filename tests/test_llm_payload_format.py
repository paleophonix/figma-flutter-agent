"""Tests for labeled LLM user payload formatting."""

from __future__ import annotations

from figma_flutter_agent.llm.payload_format import (
    dump_json_for_llm_payload,
    format_labeled_user_payload,
    parse_labeled_user_payload,
)


def test_format_labeled_user_payload_uses_compact_json() -> None:
    text = format_labeled_user_payload(
        mode="generate",
        output_schema="FlutterGenerationResponse",
        sections={"featureName": "demo", "nested": {"a": 1, "b": [1, 2]}},
    )
    assert "\n  " not in text.split("### nested", 1)[1]
    assert dump_json_for_llm_payload({"a": 1}) == '{"a":1}'


def test_parse_labeled_user_payload_roundtrips_compact_sections() -> None:
    original = {"featureName": "demo", "tokens": {"colors": {"primary": "#fff"}}}
    text = format_labeled_user_payload(
        mode="generate",
        output_schema="FlutterGenerationResponse",
        sections=original,
    )
    parsed = parse_labeled_user_payload(text)
    assert parsed["featureName"] == "demo"
    assert parsed["tokens"]["colors"]["primary"] == "#fff"
