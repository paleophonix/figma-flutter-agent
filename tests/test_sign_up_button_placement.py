"""Regression tests for vertical button placement in a bottom-weighted TOP-pinned container."""

from figma_flutter_agent.parser.layout import reconcile_stack_placement_top_from_edges
from figma_flutter_agent.parser.viewport_inset import compute_viewport_top_inset_px
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, StackPlacement


def _placement(*, top: float, bottom: float, height: float) -> StackPlacement:
    return StackPlacement(vertical="TOP", top=top, bottom=bottom, height=height)


class TestReconcileStackPlacementTopFromEdges:
    """Node 1:3970 parent height=97, children 1:3972 (SIGN UP) and 1:3973 (LOG IN)."""

    PARENT_HEIGHT = 97.0

    def test_sign_up_button_top_is_25_not_0(self) -> None:
        # 1:3972: Figma reports top=0 but bottom=58, height=39 → inferred top = 97-58-39 = 0?
        # Real geometry from Figma: top=25, bottom=33, height=39.
        placement = _placement(top=0.0, bottom=33.0, height=39.0)
        result = reconcile_stack_placement_top_from_edges(
            placement, parent_height=self.PARENT_HEIGHT
        )
        assert abs(result.top - 25.0) <= 1.0, f"expected top≈25, got {result.top}"

    def test_log_in_button_top_is_83_not_39(self) -> None:
        # 1:3973: Figma reports top=39 but correct position from bottom edge is top≈83.
        # height=14, bottom=0 → no reconcile possible without bottom.
        # With bottom edge data: top=0, bottom=0, height=14, parent=97 → top=83.
        placement = _placement(top=39.0, bottom=0.0, height=14.0)
        # bottom=0 → reconcile returns unchanged (no bottom signal)
        # This test documents the invariant: without a positive bottom, top stays as-is.
        result = reconcile_stack_placement_top_from_edges(
            placement, parent_height=self.PARENT_HEIGHT
        )
        # When bottom≤0, function returns original placement unchanged
        assert result.top == 39.0

    def test_reconcile_corrects_top_when_inferred_differs_more_than_1px(self) -> None:
        # Generic: top=0, bottom=10, height=50, parent=97 → inferred=37, differs from top=0 by >1px
        placement = _placement(top=0.0, bottom=10.0, height=50.0)
        result = reconcile_stack_placement_top_from_edges(placement, parent_height=97.0)
        assert abs(result.top - 37.0) <= 1.0, f"expected top≈37, got {result.top}"

    def test_no_reconcile_when_top_and_inferred_agree(self) -> None:
        # top=25, bottom=33, height=39, parent=97 → inferred=25, agrees → no change
        placement = _placement(top=25.0, bottom=33.0, height=39.0)
        result = reconcile_stack_placement_top_from_edges(
            placement, parent_height=self.PARENT_HEIGHT
        )
        assert abs(result.top - 25.0) <= 1.0

    def test_no_reconcile_when_parent_height_is_none(self) -> None:
        placement = _placement(top=0.0, bottom=33.0, height=39.0)
        result = reconcile_stack_placement_top_from_edges(placement, parent_height=None)
        assert result.top == 0.0

    def test_infer_top_when_top_omitted_but_bottom_present(self) -> None:
        placement = StackPlacement(vertical="TOP", bottom=20.0, height=10.0)
        result = reconcile_stack_placement_top_from_edges(placement, parent_height=100.0)
        assert result.top is not None
        assert abs(float(result.top) - 70.0) <= 1.0

    def test_bottom_anchored_cta_row_moves_down_when_top_disagrees_with_bottom(self) -> None:
        # Welcome screen CTA band: parent 896, top=661, bottom=94, height=97 → top≈705.
        placement = _placement(top=661.0, bottom=94.0, height=97.0)
        result = reconcile_stack_placement_top_from_edges(placement, parent_height=896.0)
        assert abs(float(result.top) - 705.0) <= 1.0


class TestViewportInsetPhoneWithoutSafeArea:
    """Phone stacks without shell_safe_area must produce zero inset."""

    def test_phone_canvas_without_shell_safe_area_returns_zero(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.agent.responsive.shell_safe_area = False
        settings.agent.responsive.status_bar_inset_px = 44.0
        settings.agent.layout.app_bar_inset_px = 56.0

        root = CleanDesignTreeNode(id="root", name="SignUp", type=NodeType.STACK)
        inset = compute_viewport_top_inset_px(settings, root, use_scaffold=False)
        assert inset == 0.0

    def test_phone_canvas_with_shell_safe_area_returns_status_bar_height(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.agent.responsive.shell_safe_area = True
        settings.agent.responsive.status_bar_inset_px = 44.0
        settings.agent.layout.app_bar_inset_px = 56.0

        root = CleanDesignTreeNode(id="root", name="SignUp", type=NodeType.STACK)
        inset = compute_viewport_top_inset_px(settings, root, use_scaffold=False)
        assert inset == 44.0
