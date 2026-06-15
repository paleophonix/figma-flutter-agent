"""Track A render profile, truth snapshot, and pixel oracle tests."""

from __future__ import annotations

from figma_flutter_agent.config.fidelity_policy import (
    RenderProfile,
    pixel_fidelity_policy_for_agent,
    resolve_render_profile,
)
from figma_flutter_agent.config.profiles import apply_pixel_fidelity_profile
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.generator.ir.fidelity.router import EmitPath, FidelityRoutePolicy, route_with_policy
from figma_flutter_agent.generator.visual.renderer import should_use_visual_renderer
from figma_flutter_agent.parser.truth_snapshot import (
    VISUAL_PIXEL_FORBIDDEN_MUTATIONS,
    capture_truth_snapshot,
    forbidden_mutation,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, FidelityTier, NodeType, Sizing, WidgetIrKind, WidgetIrNode
from figma_flutter_agent.validation.pixel.models import SplitPixelDiffResult
from figma_flutter_agent.validation.pixel.perfect_gate import passed_pixel_perfect_gate


def test_pixel_profile_sets_visual_render_profile() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    assert settings.agent.generation.render_profile == "visual_pixel"
    assert resolve_render_profile(settings.agent) == RenderProfile.VISUAL_PIXEL
    assert should_use_visual_renderer(settings)


def test_pixel_fidelity_policy_strict_oracle() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    policy = pixel_fidelity_policy_for_agent(settings.agent)
    assert policy.channel_tolerance == 2
    assert policy.blocking_text_diff is True
    assert policy.preserve_raw_geometry is True


def test_truth_snapshot_immutable_copy() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[],
    )
    truth = capture_truth_snapshot(tree)
    mutated = tree.model_copy(
        update={"sizing": tree.sizing.model_copy(update={"width": 200.0})},
        deep=True,
    )
    assert truth.sizing.width == 100.0
    assert mutated.sizing.width == 200.0


def test_forbidden_mutation_under_visual_pixel() -> None:
    assert forbidden_mutation("sectionize", visual_pixel=True)
    assert "sectionize" in VISUAL_PIXEL_FORBIDDEN_MUTATIONS
    assert not forbidden_mutation("sectionize", visual_pixel=False)


def test_strict_visual_fidelity_routes_unverified_to_geometric() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_UNVERIFIED,
    )
    policy = FidelityRoutePolicy(strict_visual_fidelity=True)
    assert route_with_policy(ir, policy=policy) == EmitPath.GEOMETRIC_FALLBACK


def test_pixel_perfect_gate_blocks_text_diff() -> None:
    result = SplitPixelDiffResult(
        non_text_pixel_diff=0.0,
        text_region_pixel_diff=0.01,
        text_bounds_delta=0.0,
        non_text_pixel_max=0.0,
        text_region_pixel_max=0.0,
        text_bounds_delta_max=0.0,
        text_validation_passed=True,
    )
    assert not passed_pixel_perfect_gate(result, blocking_text=True)
    assert passed_pixel_perfect_gate(result, blocking_text=False)


def test_b3_strict_product_fidelity_blocks_baked_localizable_text() -> None:
    from figma_flutter_agent.generator.ir.fidelity.text_policy import (
        TextPolicyClass,
        baked_tier_allowed_for_policy,
    )

    assert not baked_tier_allowed_for_policy(
        TextPolicyClass.LIVE_LOCALIZABLE,
        strict_fidelity=False,
        strict_l10n=False,
        strict_a11y=False,
    )
    assert not baked_tier_allowed_for_policy(
        TextPolicyClass.LIVE_LOCALIZABLE,
        strict_fidelity=False,
        strict_l10n=True,
        strict_a11y=False,
    )
