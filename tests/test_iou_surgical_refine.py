"""AC-3: surgical refine scopes LLM payload to failing widgets."""

from __future__ import annotations

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.llm.repair import build_visual_refine_user_payload
from figma_flutter_agent.schemas import DesignTokens, FlutterGenerationResponse
from figma_flutter_agent.validation.iou import WidgetDiffScore, select_surgical_targets
from figma_flutter_agent.validation.surgical_refine import build_surgical_snippets


def _large_screen() -> str:
    lines = [
        "class DemoScreen extends StatelessWidget {",
        "  @override",
        "  Widget build(BuildContext context) {",
        "    return Stack(",
        "      children: [",
    ]
    for index in range(80):
        lines.append(f"        Text('line {index}'),")
    lines.extend(
        [
            "        Positioned(",
            "          key: ValueKey('figma-social-row'),",
            "          left: 40.0,",
            "          top: 380.0,",
            "          width: 334.0,",
            "          height: 56.0,",
            "          child: Text('GOOGLE'),",
            "        ),",
            "      ],",
            "    );",
            "  }",
            "}",
        ]
    )
    return "\n".join(lines)


def test_select_surgical_targets_limits_count() -> None:
    scores = [
        WidgetDiffScore("a", 0.5, 0, 0, 10, 10),
        WidgetDiffScore("b", 0.4, 0, 0, 10, 10),
        WidgetDiffScore("c", 0.3, 0, 0, 10, 10),
        WidgetDiffScore("d", 0.01, 0, 0, 10, 10),
    ]
    targets = select_surgical_targets(scores, max_widgets=2)
    assert targets == ["a", "b"]


def test_surgical_snippets_are_small_fraction_of_screen() -> None:
    screen = _large_screen()
    snippets = build_surgical_snippets(screen, ["social-row"])
    assert "social-row" in snippets
    assert len(snippets["social-row"]) < len(screen) * 0.15


def test_visual_refine_payload_includes_surgical_snippets() -> None:
    tree = load_layout_tree("sign_up_and_sign_in")
    screen = _large_screen()
    snippets = build_surgical_snippets(screen, ["social-row"])
    generation = FlutterGenerationResponse(
        screen_code=screen,
        extracted_widgets=[],
    )
    from figma_flutter_agent.llm.payload_format import parse_labeled_user_payload

    payload = parse_labeled_user_payload(
        build_visual_refine_user_payload(
            feature_name="sign_up_and_sign_in",
            clean_tree=tree,
            tokens=DesignTokens(),
            asset_manifest=[],
            current_generation=generation,
            changed_ratio=0.2,
            threshold=0.1,
            surgical_widget_snippets=snippets,
        )
    )
    assert payload["refineMode"] == "surgical_widgets"
    assert "social-row" in payload["surgicalWidgetSnippets"]
