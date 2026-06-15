"""Multimodal content builders for Anthropic and OpenAI-compatible providers."""

from __future__ import annotations

import base64

from figma_flutter_agent.llm.prompts import (
    FIGMA_REFERENCE_INLINE_LABEL,
    FIGMA_REFERENCE_ONLY_LABEL,
    FLUTTER_RENDER_INLINE_LABEL,
    REFERENCE_USER_PREAMBLE,
    VISUAL_DIFF_INLINE_LABEL,
    VISUAL_REFINE_IMAGE_INTRO,
    VISUAL_REFINE_USER_PREAMBLE,
)

__all__ = [
    "VISUAL_REFINE_USER_PREAMBLE",
    "_encode_png_base64",
    "_is_visual_refine_attachment",
    "_build_anthropic_user_content",
    "_build_openai_user_content",
]


def _encode_png_base64(png_bytes: bytes) -> str:
    return base64.standard_b64encode(png_bytes).decode("ascii")


def _is_visual_refine_attachment(
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None,
) -> bool:
    return figma_reference_png is not None and flutter_render_png is not None


def _build_anthropic_user_content(
    prompt: str,
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None = None,
    visual_diff_png: bytes | None = None,
    *,
    user_preamble: str = REFERENCE_USER_PREAMBLE,
) -> str | list[dict[str, object]]:
    if figma_reference_png is None and flutter_render_png is None:
        return prompt
    content: list[dict[str, object]] = []
    visual_refine = _is_visual_refine_attachment(figma_reference_png, flutter_render_png)
    if visual_refine:
        content.append({"type": "text", "text": VISUAL_REFINE_IMAGE_INTRO})
    if figma_reference_png is not None:
        figma_label = FIGMA_REFERENCE_INLINE_LABEL if visual_refine else FIGMA_REFERENCE_ONLY_LABEL
        content.append({"type": "text", "text": figma_label})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(figma_reference_png),
                },
            }
        )
    if flutter_render_png is not None:
        content.append({"type": "text", "text": FLUTTER_RENDER_INLINE_LABEL})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(flutter_render_png),
                },
            }
        )
    if visual_diff_png is not None:
        content.append({"type": "text", "text": VISUAL_DIFF_INLINE_LABEL})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode_png_base64(visual_diff_png),
                },
            }
        )
    content.append({"type": "text", "text": f"{user_preamble}{prompt}"})
    return content


def _build_openai_user_content(
    prompt: str,
    figma_reference_png: bytes | None,
    flutter_render_png: bytes | None = None,
    visual_diff_png: bytes | None = None,
    *,
    user_preamble: str = REFERENCE_USER_PREAMBLE,
) -> str | list[dict[str, object]]:
    if figma_reference_png is None and flutter_render_png is None:
        return prompt
    content: list[dict[str, object]] = []
    visual_refine = _is_visual_refine_attachment(figma_reference_png, flutter_render_png)
    if visual_refine:
        content.append({"type": "text", "text": VISUAL_REFINE_IMAGE_INTRO})
    if figma_reference_png is not None:
        figma_label = FIGMA_REFERENCE_INLINE_LABEL if visual_refine else FIGMA_REFERENCE_ONLY_LABEL
        content.append({"type": "text", "text": figma_label})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(figma_reference_png)}",
                },
            }
        )
    if flutter_render_png is not None:
        content.append({"type": "text", "text": FLUTTER_RENDER_INLINE_LABEL})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(flutter_render_png)}",
                },
            }
        )
    if visual_diff_png is not None:
        content.append({"type": "text", "text": VISUAL_DIFF_INLINE_LABEL})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_png_base64(visual_diff_png)}",
                },
            }
        )
    content.append({"type": "text", "text": f"{user_preamble}{prompt}"})
    return content
