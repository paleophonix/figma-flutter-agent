"""Font diagnostics for doctor and interactive wizard check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from figma_flutter_agent.fonts.collector import collect_font_faces_from_figma_document
from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.diagnostic_models import (
    DesignFontFaceStatus,
    FontAuditRow,
)
from figma_flutter_agent.fonts.local import (
    FontMatchKind,
    classify_local_font_match,
    list_legacy_font_basenames,
)
from figma_flutter_agent.fonts.naming_hint import RENAME_IF_PRESENT_HINT, analog_usage_warning
from figma_flutter_agent.fonts.offers import (
    collect_font_download_offers,
    format_download_offer_line,
)
from figma_flutter_agent.fonts.paths import is_valid_font_bytes, project_fonts_dir
from figma_flutter_agent.schemas import FontFaceRequirement


def _face_design_label(face: FontFaceRequirement) -> tuple[str, str, str | None]:
    return face.figma_family, face.font_weight, face.font_style


def list_valid_font_files(project_dir: Path) -> tuple[list[str], list[str]]:
    """Return valid and invalid basenames under ``assets/fonts/``."""
    fonts_dir = project_fonts_dir(project_dir)
    if not fonts_dir.is_dir():
        return [], []
    valid: list[str] = []
    invalid: list[str] = []
    for path in sorted(fonts_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            invalid.append(path.name)
            continue
        if is_valid_font_bytes(payload):
            valid.append(path.name)
        else:
            invalid.append(path.name)
    return valid, invalid


def list_design_font_statuses(
    dump_path: Path,
    project_dir: Path,
) -> tuple[DesignFontFaceStatus, ...]:
    """Map each font face in a Figma dump to exact or missing local files."""
    document = json.loads(dump_path.read_text(encoding="utf-8"))
    faces = collect_font_faces_from_figma_document(document)
    context = FontResolutionContext.for_project(project_dir)
    rows: list[DesignFontFaceStatus] = []
    for face in faces:
        entry = context.lookup(face.figma_family)
        pubspec = entry.pubspec_family if entry is not None else None
        match = classify_local_font_match(face, project_dir, pubspec_family=pubspec)
        family, weight, style = _face_design_label(face)
        rows.append(
            DesignFontFaceStatus(
                family=family,
                weight=weight,
                style=style,
                expected_basename=match.expected_basename,
                found_basename=match.path.name if match.path is not None else None,
                match=match.kind,
            )
        )
    return tuple(rows)


def audit_assets_fonts(project_dir: Path) -> FontAuditRow:
    """Scan ``assets/fonts/`` for valid and corrupt files."""
    valid, invalid = list_valid_font_files(project_dir)
    if not project_fonts_dir(project_dir).is_dir():
        return FontAuditRow(
            name="assets/fonts",
            ok=True,
            detail="directory missing (created on fetch/generate)",
        )
    if invalid:
        return FontAuditRow(
            name="assets/fonts",
            ok=False,
            detail=f"{len(valid)} valid, {len(invalid)} corrupt: {', '.join(invalid)}",
        )
    if valid:
        return FontAuditRow(
            name="assets/fonts",
            ok=True,
            detail=f"{len(valid)} file(s) on disk",
        )
    return FontAuditRow(name="assets/fonts", ok=True, detail="empty")


def audit_design_fonts(dump_path: Path, project_dir: Path) -> FontAuditRow:
    """Summarize whether design faces use exact canonical filenames."""
    if not dump_path.is_file():
        return FontAuditRow(
            name="design fonts",
            ok=False,
            detail=f"dump missing: {dump_path.as_posix()}",
        )

    statuses = list_design_font_statuses(dump_path, project_dir)
    if not statuses:
        return FontAuditRow(name="design fonts", ok=True, detail="no font faces in dump")

    exact = sum(1 for item in statuses if item.match == "exact")
    analog = sum(1 for item in statuses if item.match == "analog")
    missing = sum(1 for item in statuses if item.match == "missing")
    ok = missing == 0
    parts = [f"{exact}/{len(statuses)} exact names"]
    if analog:
        parts.append(f"{analog} analog substitute(s)")
    if missing:
        parts.append(f"{missing} missing (rename/copy required)")
    return FontAuditRow(
        name="design fonts",
        ok=ok,
        detail=", ".join(parts),
    )


def collect_font_filename_warnings(
    faces: tuple[FontFaceRequirement, ...] | list[FontFaceRequirement],
    project_dir: Path,
) -> list[str]:
    """Warnings for analog-on-disk faces and missing faces (with download offers)."""
    context = FontResolutionContext.for_project(project_dir)
    warnings: list[str] = []
    missing_faces: list[FontFaceRequirement] = []
    for face in faces:
        entry = context.lookup(face.figma_family)
        pubspec = entry.pubspec_family if entry is not None else None
        match = classify_local_font_match(face, project_dir, pubspec_family=pubspec)
        if match.kind == "analog" and match.path is not None:
            warnings.append(
                analog_usage_warning(
                    face,
                    pubspec_family=pubspec,
                    substitute_label="on disk",
                    saved_as=match.path.name,
                )
            )
        elif match.kind == "missing":
            missing_faces.append(face)
    for offer in collect_font_download_offers(missing_faces, project_dir):
        warnings.append(format_download_offer_line(offer))
    return warnings


def collect_font_audit_rows(
    project_dir: Path,
    *,
    dump_path: Path | None = None,
) -> tuple[FontAuditRow, ...]:
    """Run assets scan and optional design-font coverage for one dump."""
    rows = [audit_assets_fonts(project_dir)]
    if dump_path is not None:
        rows.append(audit_design_fonts(dump_path, project_dir))
    return tuple(rows)


def _status_tag(match: FontMatchKind) -> str:
    if match == "exact":
        return "OK exact"
    if match == "analog":
        return "ANALOG"
    return "MISSING"


def format_wizard_font_report(
    project_dir: Path,
    *,
    dump_path: Path | None,
    screen: str | None,
    scope: Literal["assets", "screen", "full"] = "full",
) -> tuple[bool, list[str]]:
    """Build human-readable font audit lines for the interactive wizard.

    Args:
        project_dir: Flutter project root.
        dump_path: Cached Figma frame JSON for design-font comparison.
        screen: Active screen slug for report headers.
        scope: ``assets`` lists on-disk files only; ``screen`` compares the
            dump to ``assets/fonts/`` without listing unrelated files;
            ``full`` includes both design coverage and the full disk inventory.
    """
    lines: list[str] = []
    valid_files, invalid_files = list_valid_font_files(project_dir)

    if scope == "assets" or dump_path is None or not dump_path.is_file():
        if scope == "screen":
            lines.append("[red]No screen dump available for design-font audit.[/red]")
            return False, lines
        lines.append("[bold]assets/fonts/[/bold]")
        if not project_fonts_dir(project_dir).is_dir():
            lines.append("[dim]directory missing (created on fetch/generate)[/dim]")
        elif valid_files:
            lines.append(f"{len(valid_files)} file(s) on disk:")
            for name in valid_files:
                lines.append(f"  • {name}")
        else:
            lines.append("[dim](empty)[/dim]")
        if invalid_files:
            lines.append(f"[red]Corrupt:[/red] {', '.join(invalid_files)}")
        legacy_names = list_legacy_font_basenames(project_dir)
        if legacy_names:
            lines.append("")
            lines.append(
                "[yellow]Deprecated project fonts/ folder[/yellow] — agent uses "
                "[bold]assets/fonts/[/bold] only:"
            )
            for name in legacy_names:
                lines.append(f"  • fonts/{name}")
        return len(invalid_files) == 0, lines

    statuses = list_design_font_statuses(dump_path, project_dir)
    exact = sum(1 for item in statuses if item.match == "exact")
    analog = sum(1 for item in statuses if item.match == "analog")
    missing = sum(1 for item in statuses if item.match == "missing")
    passed = missing == 0 and not invalid_files

    header = f"Required by design ({len(statuses)} face(s))"
    if screen:
        header = f"{header} — screen [bold]{screen}[/bold]"
    lines.append(header)

    for item in statuses:
        style = f" {item.style}" if item.style else ""
        lines.append(f"  [bold]{item.family}[/bold]  {item.weight}{style}")
        lines.append(f"    need:  assets/fonts/{item.expected_basename}")
        if item.match == "exact":
            lines.append(f"    have:  {item.found_basename}  [green]{_status_tag(item.match)}[/green]")
        elif item.match == "analog":
            lines.append(
                f"    have:  {item.found_basename}  [yellow]{_status_tag(item.match)}[/yellow]"
            )
            orig = item.expected_basename.split(" (original)", 1)[0]
            lines.append(f"    → original not present; need [cyan]{orig}[/cyan] for exact match")
        else:
            orig = item.expected_basename.split(" (original)", 1)[0]
            lines.append(f"    have:  —  [red]{_status_tag(item.match)}[/red]")
            lines.append(f"    → copy/rename to [cyan]{orig}[/cyan]")

    summary_parts: list[str] = []
    if exact:
        summary_parts.append(f"{exact} exact")
    if analog:
        summary_parts.append(f"{analog} analog")
    if missing:
        summary_parts.append(f"{missing} missing")
    summary = ", ".join(summary_parts) if summary_parts else "no fonts in dump"
    lines.append("")
    if passed and analog == 0:
        lines.append(f"[green]Summary:[/green] {summary} — ready for run/generate.")
    elif passed and analog:
        lines.append(
            f"[yellow]Summary:[/yellow] {summary} — analog substitutes on disk; "
            "add originals for exact match."
        )
    else:
        lines.append(
            f"[yellow]Summary:[/yellow] {summary} — only exact filenames count as OK; "
            "rename/copy in assets/fonts/ or enable fonts.download_fonts."
        )
    lines.append(f"[dim]{RENAME_IF_PRESENT_HINT}[/dim]")

    document = json.loads(dump_path.read_text(encoding="utf-8"))
    faces = collect_font_faces_from_figma_document(document)
    offers = collect_font_download_offers(faces, project_dir)
    if offers:
        lines.append("")
        lines.append(
            "[yellow]Substitutes available[/yellow] (not auto-downloaded; "
            "set [bold]fonts.download_fonts: true[/bold] or add originals):"
        )
        for offer in offers:
            lines.append(f"  • assets/fonts/[cyan]{offer.asset_name}[/cyan] — {offer.source_label}")

    if scope == "full":
        lines.append("")
        lines.append(f"In assets/fonts/ ({len(valid_files)} file(s) on disk):")
        if valid_files:
            for name in valid_files:
                lines.append(f"  • {name}")
        else:
            lines.append("  [dim](empty)[/dim]")

        legacy_names = list_legacy_font_basenames(project_dir)
        if legacy_names:
            lines.append("")
            lines.append(
                "[yellow]Deprecated project fonts/ folder[/yellow] — agent uses "
                "[bold]assets/fonts/[/bold] only; safe to delete fonts/ after moving files:"
            )
            for name in legacy_names:
                lines.append(f"  • fonts/{name}")

    if invalid_files:
        lines.append(f"[red]Corrupt files:[/red] {', '.join(invalid_files)}")
        passed = False

    return passed, lines
