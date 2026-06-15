"""Font diagnostics for wizard check and doctor."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.fonts.bundle import bundle_font_faces
from figma_flutter_agent.fonts.diagnostics import (
    audit_design_fonts,
    collect_font_filename_warnings,
    format_wizard_font_report,
    list_design_font_statuses,
)
from figma_flutter_agent.fonts.local import (
    classify_local_font_match,
    expected_analog_asset_name,
)
from figma_flutter_agent.fonts.paths import is_valid_font_bytes
from figma_flutter_agent.schemas import FontFaceRequirement


def _minimal_ttf_payload() -> bytes:
    return b"\x00\x01\x00\x00" + (b"\x00" * 252)


def test_is_valid_font_bytes_rejects_placeholders() -> None:
    assert not is_valid_font_bytes(b"regular-font")
    assert is_valid_font_bytes(_minimal_ttf_payload())


def test_wrong_filename_is_missing_not_matched(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "HelveticaNeue-Medium.otf").write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")
    match = classify_local_font_match(face, tmp_path)
    assert match.kind == "missing"
    assert match.path is None

    dump = tmp_path / "dump.json"
    dump.write_text(
        """
        {
          "type": "FRAME",
          "children": [{
            "type": "TEXT",
            "style": {"fontFamily": "Helvetica Neue", "fontWeight": 500}
          }]
        }
        """,
        encoding="utf-8",
    )

    statuses = list_design_font_statuses(dump, tmp_path)
    assert statuses[0].match == "missing"
    assert statuses[0].found_basename is None

    row = audit_design_fonts(dump, tmp_path)
    assert row.ok is False
    assert "missing" in row.detail


def test_collect_font_filename_warnings_when_exact_name_missing(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "HelveticaNeue-Medium.otf").write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")
    warnings = collect_font_filename_warnings([face], tmp_path)
    assert warnings
    assert "helvetica_neue_500" in warnings[0]
    assert (
        "substitute available" in warnings[0].lower() or "place the original" in warnings[0].lower()
    )


def test_exact_filename_matches(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "helvetica_neue_500.otf").write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")
    match = classify_local_font_match(face, tmp_path)
    assert match.kind == "exact"
    assert match.path is not None


def test_bundle_font_faces_warns_without_exact_file(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "HelveticaNeue-Medium.otf").write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")
    manifest = bundle_font_faces([face], tmp_path, download_fonts=False, phase="run")
    assert any("helvetica_neue_500" in w for w in manifest.warnings)


def test_format_wizard_font_report_lists_need_and_missing(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "HelveticaNeue-Medium.otf").write_bytes(_minimal_ttf_payload())
    (fonts_dir / "arial_700.ttf").write_bytes(_minimal_ttf_payload())

    dump = tmp_path / "dump.json"
    dump.write_text(
        """
        {
          "type": "FRAME",
          "children": [
            {"type": "TEXT", "style": {"fontFamily": "Helvetica Neue", "fontWeight": 500}},
            {"type": "TEXT", "style": {"fontFamily": "Arial", "fontWeight": 400}}
          ]
        }
        """,
        encoding="utf-8",
    )

    passed, lines = format_wizard_font_report(
        tmp_path,
        dump_path=dump,
        screen="sign_in",
        scope="full",
    )
    text = "\n".join(lines)
    assert passed is False
    assert "need:" in text
    assert "MISSING" in text
    assert "helvetica_neue_500" in text
    assert "HelveticaNeue-Medium.otf" in text
    assert "exact filenames" in text


def test_analog_on_disk_warns_and_reports_analog(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    analog_name = expected_analog_asset_name("Helvetica Neue", 500, None, ext=".otf")
    (fonts_dir / analog_name).write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")
    match = classify_local_font_match(face, tmp_path)
    assert match.kind == "analog"
    assert match.path is not None

    warnings = collect_font_filename_warnings([face], tmp_path)
    assert warnings
    assert "analog" in warnings[0].lower()

    dump = tmp_path / "dump.json"
    dump.write_text(
        """
        {
          "type": "FRAME",
          "children": [{
            "type": "TEXT",
            "style": {"fontFamily": "Helvetica Neue", "fontWeight": 500}
          }]
        }
        """,
        encoding="utf-8",
    )
    passed, lines = format_wizard_font_report(tmp_path, dump_path=dump, screen="x")
    text = "\n".join(lines)
    assert "ANALOG" in text
    assert analog_name in text
    assert passed is True


def test_format_wizard_font_report_screen_scope_omits_full_disk_inventory(
    tmp_path: Path,
) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "helvetica_neue_500.otf").write_bytes(_minimal_ttf_payload())
    (fonts_dir / "unused_extra_font.ttf").write_bytes(_minimal_ttf_payload())

    dump = tmp_path / "dump.json"
    dump.write_text(
        """
        {
          "type": "FRAME",
          "children": [{
            "type": "TEXT",
            "style": {"fontFamily": "Helvetica Neue", "fontWeight": 500}
          }]
        }
        """,
        encoding="utf-8",
    )

    passed, lines = format_wizard_font_report(
        tmp_path,
        dump_path=dump,
        screen="feedback",
        scope="screen",
    )
    text = "\n".join(lines)
    assert passed is True
    assert "Required by design (1 face(s))" in text
    assert "unused_extra_font.ttf" not in text
    assert "In assets/fonts/" not in text
