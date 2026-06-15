"""T2 baked asset emit for semantic IR nodes (EPIC 4.5)."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.schemas import CleanDesignTreeNode, WidgetIrNode


def _first_asset_host(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the first subtree node that carries an exported raster or vector asset."""
    if node.image_asset_key or node.vector_asset_key:
        return node
    for child in node.children:
        found = _first_asset_host(child)
        if found is not None:
            return found
    return None


def emit_baked_asset(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    ctx: IrEmitContext,
) -> str:
    """Emit ``Image.asset`` or ``SvgPicture`` for a baked fidelity tier node.

    Args:
        ir: Semantic IR node stamped with ``svg_baked`` or ``png_baked``.
        clean: Matching clean-tree subtree with exported asset keys.
        ctx: Emit context (``uses_svg`` controls SVG vs raster preference).

    Returns:
        Dart widget expression for the baked export.

    Raises:
        GenerationError: When no exportable asset key exists on the subtree.
    """
    asset_host = _first_asset_host(clean)
    if asset_host is None:
        raise GenerationError(
            "Baked fidelity tier has no exportable asset on clean tree "
            f"(figmaId={ir.figma_id!r}, kind={ir.kind.value}, tier={ir.fidelity_tier!r})"
        )

    from figma_flutter_agent.generator.layout.widgets.svg import _render_exported_vector

    body = _render_exported_vector(asset_host, uses_svg=ctx.uses_svg)
    if body is None:
        raise GenerationError(
            "Baked fidelity tier asset could not be rendered "
            f"(figmaId={ir.figma_id!r}, kind={ir.kind.value}, tier={ir.fidelity_tier!r})"
        )
    return body
