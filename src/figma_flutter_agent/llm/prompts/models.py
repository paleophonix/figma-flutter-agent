"""Prompt dataclasses and multimodal labels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CpiSupervisorContext:
    """Runtime bindings for the metacognitive repair-loop supervisor prompt."""

    last_patches: str
    recurring_errors: str
    figma_node_intent: str


@dataclass(frozen=True, slots=True)
class MultimodalUserLabels:
    """Text prepended to multimodal user messages (not LLM system prompts)."""

    reference_preamble: str
    figma_only: str
    figma_inline: str
    flutter_render_inline: str
    visual_diff_inline: str
    refine_intro: str
    refine_preamble: str


USER_LABELS = MultimodalUserLabels(
    reference_preamble=(
        "Attached PNG: golden-standard Figma export of the target screen. "
        "Match this reference as closely as valid Flutter layout rules allow.\n\n"
    ),
    figma_only=(
        "[[FIGMA REFERENCE — TARGET DESIGN]] "
        "Golden-standard Figma export of the target screen frame. "
        "Match this reference — it is NOT the Flutter output.\n"
    ),
    figma_inline=(
        "[[IMAGE 1 — FIGMA REFERENCE (TARGET)]] "
        "Authoritative Figma frame export. This is the design you MUST match. "
        "Do NOT treat this image as the Flutter output.\n"
    ),
    flutter_render_inline=(
        "[[IMAGE 2 — FLUTTER RENDER (CURRENT OUTPUT)]] "
        "Current Flutter golden screenshot from generated code. "
        "This is what you are fixing — move it toward IMAGE 1; never treat IMAGE 2 as the target.\n"
    ),
    visual_diff_inline=(
        "[[IMAGE 3 — VISUAL DIFF HEATMAP]] "
        "Pixel delta vs IMAGE 1: mismatches highlighted in RED on the Figma layout. "
        "Use this as an error map — do not treat red pixels as desired design.\n"
    ),
    refine_intro=(
        "Three images follow in fixed order. Each has an inline label immediately before its image block. "
        "Confirm roles via attachedImages in the JSON below.\n\n"
    ),
    refine_preamble=(
        "Attached images (fixed order — do not swap):\n"
        "- IMAGE 1 / figma_reference: Figma golden-standard export (TARGET design).\n"
        "- IMAGE 2 / flutter_render: current Flutter golden render (CURRENT output to refine).\n"
        "- IMAGE 3 / visual_diff_heatmap: red-on-Figma mismatch map (ERROR LOG vs target).\n"
        "Start from IMAGE 3 red zones → Dart code, then IMAGE 1 ↔ IMAGE 2, then CODE ↔ interactivity. "
        "Use refineHistory when present to avoid repeating failed strategies.\n\n"
    ),
)

REFERENCE_USER_PREAMBLE = USER_LABELS.reference_preamble
FIGMA_REFERENCE_ONLY_LABEL = USER_LABELS.figma_only
FIGMA_REFERENCE_INLINE_LABEL = USER_LABELS.figma_inline
FLUTTER_RENDER_INLINE_LABEL = USER_LABELS.flutter_render_inline
VISUAL_DIFF_INLINE_LABEL = USER_LABELS.visual_diff_inline
VISUAL_REFINE_IMAGE_INTRO = USER_LABELS.refine_intro
VISUAL_REFINE_USER_PREAMBLE = USER_LABELS.refine_preamble

_REFINE_IMAGE_ROLES: tuple[dict[str, str | int], ...] = (
    {
        "index": 1,
        "role": "figma_reference",
        "label": "FIGMA REFERENCE (TARGET)",
        "description": "Authoritative Figma frame export — the design to match.",
        "attachmentHint": "First labeled image block above this JSON.",
    },
    {
        "index": 2,
        "role": "flutter_render",
        "label": "FLUTTER RENDER (CURRENT OUTPUT)",
        "description": "Current Flutter golden from generated code — refine toward image 1.",
        "attachmentHint": "Second labeled image block above this JSON.",
    },
    {
        "index": 3,
        "role": "visual_diff_heatmap",
        "label": "VISUAL DIFF HEATMAP",
        "description": "Red-highlighted pixel deltas vs Figma — map red zones to code fixes.",
        "attachmentHint": "Third labeled image block above this JSON.",
    },
)
