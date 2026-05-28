"""M4: surgical patch apply round-trip without LLM or Docker."""

from __future__ import annotations

from figma_flutter_agent.validation.surgical_refine import (
    apply_surgical_patches,
    build_surgical_snippets,
    extract_widget_snippet,
)


def _screen_with_social_row() -> str:
    return "\n".join(
        [
            "class DemoScreen extends StatelessWidget {",
            "  @override",
            "  Widget build(BuildContext context) {",
            "    return Stack(",
            "      children: [",
            "        Positioned(",
            "          key: ValueKey('figma-social-row'),",
            "          left: 40.0,",
            "          top: 380.0,",
            "          width: 334.0,",
            "          height: 56.0,",
            "          child: Text('OLD'),",
            "        ),",
            "      ],",
            "    );",
            "  }",
            "}",
        ]
    )


def test_m4_extract_and_apply_surgical_patch() -> None:
    screen = _screen_with_social_row()
    snippet = extract_widget_snippet(screen, "social-row")
    assert snippet is not None
    assert "OLD" in snippet

    replacement = snippet.replace("OLD", "NEW")
    patched = apply_surgical_patches(screen, {"social-row": replacement})
    assert "NEW" in patched
    assert "OLD" not in patched
    snippets = build_surgical_snippets(patched, ["social-row"])
    assert "social-row" in snippets
    assert "NEW" in snippets["social-row"]
