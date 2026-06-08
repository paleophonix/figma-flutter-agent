import pytest

from figma_flutter_agent.parser.tokens.naming import allocate_token_name, sanitize_token_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2x Padding", "t2xPadding"),
        ("class", "tClass"),
        ("Brand/Primary", "brandPrimary"),
    ],
)
def test_sanitize_token_name_is_dart_safe(raw: str, expected: str) -> None:
    assert sanitize_token_name(raw) == expected


def test_allocate_token_name_deduplicates_collisions() -> None:
    used: set[str] = set()
    assert allocate_token_name("primary", used) == "primary"
    assert allocate_token_name("primary", used) == "primary2"
    assert allocate_token_name("primary", used) == "primary3"
