"""Tests for two-stage TEXT mask pixel diff."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)
from figma_flutter_agent.validation.pixeldiff import (
    DictFlutterCoordinateMapper,
    collect_text_mask_rects,
    compare_png_files_with_text_mask,
    mask_text_regions,
    validate_text_coordinates,
)


def _text_node(
    node_id: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Label",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width=width, height=height),
        stack_placement=StackPlacement(left=left, top=top, width=width, height=height),
    )


def _screen_tree(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100, height=100),
        children=list(children),
    )


def _write_png(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (100, 100), color).save(path)


def test_validate_text_coordinates_fails_on_displacement() -> None:
    tree = _screen_tree(_text_node("1:10", left=10, top=20, width=40, height=12))
    mapper = DictFlutterCoordinateMapper(
        rects_by_token={"1_10": (13.0, 26.0, 40.0, 12.0)},
    )
    outcome = validate_text_coordinates(
        tree,
        mapper,
        tolerance=3,
        image_width=100,
        image_height=100,
    )
    assert not outcome.passed
    assert outcome.failures[0].node_id == "1:10"
    assert "layout displacement" in outcome.failures[0].repair_message()


def test_validate_text_coordinates_passes_within_tolerance() -> None:
    tree = _screen_tree(_text_node("1:10", left=10, top=20, width=40, height=12))
    mapper = DictFlutterCoordinateMapper(
        rects_by_token={"1_10": (11.0, 22.0, 40.0, 12.0)},
    )
    outcome = validate_text_coordinates(
        tree,
        mapper,
        tolerance=3,
        image_width=100,
        image_height=100,
    )
    assert outcome.passed


def test_validate_text_coordinates_skips_missing_nodes_without_error() -> None:
    tree = _screen_tree(
        _text_node("1:10", left=10, top=20, width=40, height=12),
        CleanDesignTreeNode(
            id="1:11",
            name="No placement",
            type=NodeType.TEXT,
            text="x",
        ),
    )
    mapper = DictFlutterCoordinateMapper(rects_by_token={})
    outcome = validate_text_coordinates(
        tree,
        mapper,
        tolerance=3,
        image_width=100,
        image_height=100,
    )
    assert outcome.passed


def test_masked_diff_ignores_glyph_noise(tmp_path: Path) -> None:
    tree = _screen_tree(_text_node("1:10", left=10, top=20, width=40, height=20))
    reference = tmp_path / "ref.png"
    actual = tmp_path / "act.png"
    _write_png(reference, (255, 255, 255, 255))
    _write_png(actual, (255, 255, 255, 255))
    ref_img = Image.open(reference).convert("RGBA")
    act_img = Image.open(actual).convert("RGBA")
    regions = collect_text_mask_rects(tree, image_width=100, image_height=100)
    ref_img = mask_text_regions(ref_img, regions)
    act_img = mask_text_regions(act_img, regions)
    ref_img.paste((0, 0, 0, 255), (10, 20, 50, 40))
    act_img.paste((40, 40, 40, 255), (10, 20, 50, 40))
    ref_img.save(reference)
    act_img.save(actual)

    outcome = compare_png_files_with_text_mask(
        reference.as_posix(),
        actual.as_posix(),
        clean_tree=tree,
        flutter_mapper=DictFlutterCoordinateMapper(
            rects_by_token={"1_10": (10.0, 20.0, 40.0, 20.0)},
        ),
        threshold=0.005,
        text_coordinate_tolerance=3,
    )
    assert outcome.text_validation.passed
    assert outcome.pixel.passed


def test_compare_aborts_before_pixel_diff_on_coordinate_fail(tmp_path: Path) -> None:
    tree = _screen_tree(_text_node("1:10", left=10, top=20, width=40, height=20))
    reference = tmp_path / "ref.png"
    actual = tmp_path / "act.png"
    _write_png(reference, (255, 0, 0, 255))
    _write_png(actual, (0, 255, 0, 255))
    outcome = compare_png_files_with_text_mask(
        reference.as_posix(),
        actual.as_posix(),
        clean_tree=tree,
        flutter_mapper=DictFlutterCoordinateMapper(
            rects_by_token={"1_10": (30.0, 20.0, 40.0, 20.0)},
        ),
        threshold=0.005,
        text_coordinate_tolerance=3,
    )
    assert not outcome.passed
    assert not outcome.text_validation.passed
    assert outcome.pixel.changed_ratio == 1.0
