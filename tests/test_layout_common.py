"""Tests for layout_common helpers."""

from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
    normalize_box_constraints,
    sanitize_dart_type_name,
    sanitize_figma_key_token,
    to_pascal_case,
)


def test_escape_dart_string_handles_newlines() -> None:
    assert escape_dart_string("Everyday is best, but we recommend picking\nat least five.") == (
        "Everyday is best, but we recommend picking\\nat least five."
    )


def test_escape_dart_string_handles_quotes_and_backslashes() -> None:
    assert escape_dart_string("it's a \\path") == "it\\'s a \\\\path"


def test_escape_dart_string_handles_dollar_interpolation_marker() -> None:
    assert escape_dart_string("$3.469.52") == r"\$3.469.52"
    assert escape_dart_string("Total ${amount}") == r"Total \${amount}"


def test_escape_dart_string_handles_unicode_line_terminators() -> None:
    """Dart treats U+2028/U+2029 as line terminators inside string literals."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    raw = "+ line one\n+ line two\u2028- line three"
    escaped = escape_dart_string(raw)
    assert "\u2028" not in escaped
    assert "\u2029" not in escaped
    assert "\\u2028" in escaped
    literal = f"Text('{escaped}')"
    assert validate_dart_delimiters(literal) is None

    paragraph = "block one\u2029block two"
    escaped_paragraph = escape_dart_string(paragraph)
    assert "\\u2029" in escaped_paragraph
    assert validate_dart_delimiters(f"Text('{escaped_paragraph}')") is None


def test_sanitize_dart_type_name() -> None:
    assert sanitize_dart_type_name("123-btn") == "N123_btn"
    assert sanitize_dart_type_name("") == "Feature"
    assert sanitize_dart_type_name("class") == "classWidget"


def test_to_pascal_case_sanitizes_invalid_identifiers() -> None:
    assert to_pascal_case("123 foo") == "N123Foo"


def test_sanitize_figma_key_token_whitelist() -> None:
    assert sanitize_figma_key_token("1:2\\3") == "n_1_2_3"
    assert sanitize_figma_key_token("12:34") == "n_12_34"
    assert sanitize_figma_key_token("abc-9") == "abc-9"


def test_normalize_box_constraints() -> None:
    assert normalize_box_constraints(48.0, 40.0) == (48.0, 48.0)
    assert normalize_box_constraints(40.0, 60.0) == (40.0, 60.0)
