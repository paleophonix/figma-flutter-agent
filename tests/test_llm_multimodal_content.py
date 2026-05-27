"""Tests for multimodal user message image labeling."""

from __future__ import annotations

from figma_flutter_agent.llm.client import (
    _build_anthropic_user_content,
    _build_openai_user_content,
)
from figma_flutter_agent.llm.prompts import (
    FIGMA_REFERENCE_INLINE_LABEL,
    FIGMA_REFERENCE_ONLY_LABEL,
    FLUTTER_RENDER_INLINE_LABEL,
    VISUAL_DIFF_INLINE_LABEL,
    VISUAL_REFINE_IMAGE_INTRO,
    VISUAL_REFINE_USER_PREAMBLE,
)


def _png_bytes(marker: str) -> bytes:
    return marker.encode("ascii")


def _text_blocks(content: list[dict[str, object]]) -> list[str]:
    return [str(block["text"]) for block in content if block.get("type") == "text"]


def _image_blocks(content: list[dict[str, object]]) -> list[dict[str, object]]:
    return [block for block in content if block.get("type") in {"image", "image_url"}]


def test_openai_visual_refine_labels_each_image_before_block() -> None:
    content = _build_openai_user_content(
        '{"mode":"visual_refine"}',
        _png_bytes("figma"),
        _png_bytes("flutter"),
        _png_bytes("diff"),
        user_preamble=VISUAL_REFINE_USER_PREAMBLE,
    )
    assert isinstance(content, list)
    texts = _text_blocks(content)
    images = _image_blocks(content)

    assert texts[0] == VISUAL_REFINE_IMAGE_INTRO
    assert texts[1] == FIGMA_REFERENCE_INLINE_LABEL
    assert images[0]["type"] == "image_url"
    assert texts[2] == FLUTTER_RENDER_INLINE_LABEL
    assert images[1]["type"] == "image_url"
    assert texts[3] == VISUAL_DIFF_INLINE_LABEL
    assert images[2]["type"] == "image_url"
    assert VISUAL_REFINE_USER_PREAMBLE in texts[-1]
    assert '{"mode":"visual_refine"}' in texts[-1]


def test_anthropic_visual_refine_labels_each_image_before_block() -> None:
    content = _build_anthropic_user_content(
        '{"mode":"visual_refine"}',
        _png_bytes("figma"),
        _png_bytes("flutter"),
        _png_bytes("diff"),
        user_preamble=VISUAL_REFINE_USER_PREAMBLE,
    )
    assert isinstance(content, list)
    texts = _text_blocks(content)
    images = _image_blocks(content)

    assert texts[0] == VISUAL_REFINE_IMAGE_INTRO
    assert texts[1] == FIGMA_REFERENCE_INLINE_LABEL
    assert images[0]["type"] == "image"
    assert texts[2] == FLUTTER_RENDER_INLINE_LABEL
    assert images[1]["type"] == "image"
    assert texts[3] == VISUAL_DIFF_INLINE_LABEL
    assert images[2]["type"] == "image"
    assert VISUAL_REFINE_USER_PREAMBLE in texts[-1]


def test_openai_single_figma_reference_has_target_label() -> None:
    content = _build_openai_user_content(
        '{"mode":"generate"}',
        _png_bytes("figma"),
        user_preamble="Match Figma.\n\n",
    )
    assert isinstance(content, list)
    texts = _text_blocks(content)
    assert texts[0] == FIGMA_REFERENCE_ONLY_LABEL
    assert _image_blocks(content)[0]["type"] == "image_url"
    assert "Match Figma." in texts[-1]


def test_anthropic_single_figma_reference_has_target_label() -> None:
    content = _build_anthropic_user_content(
        '{"mode":"generate"}',
        _png_bytes("figma"),
        user_preamble="Match Figma.\n\n",
    )
    assert isinstance(content, list)
    texts = _text_blocks(content)
    assert texts[0] == FIGMA_REFERENCE_ONLY_LABEL
    assert _image_blocks(content)[0]["type"] == "image"
