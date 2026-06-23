"""Regression tests for filter raster fallback asset resolution."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.widgets import SVG_PATH_RASTER_THRESHOLD
from figma_flutter_agent.parser.boundaries.assets import resolve_missing_image_asset_keys
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_resolve_filter_raster_fallback_keys_binds_png(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets" / "illustrations"
    assets_dir.mkdir(parents=True)
    png = assets_dir / "card_face.png"
    png.write_bytes(b"png")
    node = CleanDesignTreeNode(
        id="1",
        name="Card art",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=204.0),
        vector_asset_key="assets/illustrations/card_face.svg",
        vector_svg_has_filter=True,
    )
    resolve_missing_image_asset_keys(node, tmp_path)
    assert node.image_asset_key == "assets/illustrations/card_face.png"


def test_resolve_filter_raster_fallback_keys_binds_cross_folder_png(tmp_path: Path) -> None:
    illustrations = tmp_path / "assets" / "illustrations"
    images = tmp_path / "assets" / "images"
    illustrations.mkdir(parents=True)
    images.mkdir(parents=True)
    (illustrations / "render_boundary_169_21402.svg").write_text("<svg></svg>", encoding="utf-8")
    (images / "render_boundary_169_21402.png").write_bytes(b"png")
    node = CleanDesignTreeNode(
        id="169:21402",
        name="Card art",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=204.0),
        vector_asset_key="assets/illustrations/render_boundary_169_21402.svg",
        vector_svg_has_filter=True,
    )
    resolve_missing_image_asset_keys(node, tmp_path)
    assert node.image_asset_key == "assets/images/render_boundary_169_21402.png"


def test_resolve_filter_raster_fallback_keys_binds_png_for_high_path_count(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets" / "illustrations"
    assets_dir.mkdir(parents=True)
    (assets_dir / "starfield.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets_dir / "starfield.png").write_bytes(b"png")
    node = CleanDesignTreeNode(
        id="1:star",
        name="Starfield",
        type=NodeType.VECTOR,
        sizing=Sizing(width=375.0, height=812.0),
        vector_asset_key="assets/illustrations/starfield.svg",
        vector_svg_path_count=SVG_PATH_RASTER_THRESHOLD + 23,
    )
    resolve_missing_image_asset_keys(node, tmp_path)
    assert node.image_asset_key == "assets/illustrations/starfield.png"


def test_render_exported_vector_prefers_png_for_high_path_count() -> None:
    from figma_flutter_agent.generator.layout.widgets.svg import _render_exported_vector

    node = CleanDesignTreeNode(
        id="1:star",
        name="Starfield",
        type=NodeType.STACK,
        sizing=Sizing(width=376.0, height=812.0),
        vector_asset_key="assets/illustrations/starfield.svg",
        vector_svg_path_count=SVG_PATH_RASTER_THRESHOLD + 23,
        image_asset_key="assets/illustrations/starfield.png",
        render_boundary=True,
    )
    emitted = _render_exported_vector(node, uses_svg=True)
    assert emitted is not None
    assert "Image.asset('assets/illustrations/starfield.png'" in emitted
    assert "SvgPicture" not in emitted


def test_render_exported_vector_falls_back_to_svg_without_materialized_png() -> None:
    """Law: raster_tier_emit_requires_materialized_image_asset_key."""
    from figma_flutter_agent.generator.layout.widgets.svg import _render_exported_vector

    node = CleanDesignTreeNode(
        id="1:star",
        name="Starfield",
        type=NodeType.STACK,
        sizing=Sizing(width=376.0, height=812.0),
        vector_asset_key="assets/illustrations/starfield.svg",
        vector_svg_path_count=SVG_PATH_RASTER_THRESHOLD + 23,
        render_boundary=True,
    )
    emitted = _render_exported_vector(node, uses_svg=True)
    assert emitted is not None
    assert "SvgPicture.asset('assets/illustrations/starfield.svg'" in emitted
    assert ".png" not in emitted


def test_render_exported_vector_uses_svg_for_multi_child_stack_with_export_key() -> None:
    from figma_flutter_agent.generator.layout.widgets.svg import _render_exported_vector

    node = CleanDesignTreeNode(
        id="1:google",
        name="google",
        type=NodeType.STACK,
        sizing=Sizing(width=18.0, height=18.0),
        vector_asset_key="assets/icons/google_icon.svg",
        vector_svg_path_count=4,
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="path",
                type=NodeType.VECTOR,
                sizing=Sizing(width=9.0, height=9.0),
            ),
            CleanDesignTreeNode(
                id="1:2",
                name="path",
                type=NodeType.VECTOR,
                sizing=Sizing(width=9.0, height=9.0),
            ),
        ],
    )
    emitted = _render_exported_vector(node, uses_svg=True)
    assert emitted is not None
    assert "SvgPicture.asset('assets/icons/google_icon.svg'" in emitted
    assert ".png" not in emitted
