"""Wizard doctor report helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings, resolve_agent_config_path
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable, resolve_flutter_executable
from figma_flutter_agent.dev.project import resolve_manifest_path
from figma_flutter_agent.dev.wizard.models import DoctorCheck, DoctorReport
from figma_flutter_agent.fonts.diagnostics import collect_font_audit_rows


def collect_doctor_report(*, project_dir: Path, settings: Settings) -> DoctorReport:
    """Run environment checks for the interactive wizard."""
    checks: list[DoctorCheck] = []

    token = settings.figma_token().strip()
    checks.append(
        DoctorCheck(
            name="FIGMA_ACCESS_TOKEN",
            ok=bool(token),
            detail="present" if token else "missing - live sync and batch dump need a token",
        )
    )

    flutter = resolve_flutter_executable(sdk_root=settings.flutter_sdk or None)
    checks.append(
        DoctorCheck(
            name="Flutter SDK",
            ok=flutter is not None,
            detail=flutter or "not on PATH - set FIGMA_FLUTTER_SDK in .env",
        )
    )

    dart = resolve_dart_executable(sdk_root=settings.flutter_sdk or None)
    checks.append(
        DoctorCheck(
            name="Dart SDK",
            ok=dart is not None,
            detail=dart or "not on PATH (optional for analyze gates)",
        )
    )

    pubspec = project_dir / "pubspec.yaml"
    checks.append(
        DoctorCheck(
            name="Flutter project",
            ok=pubspec.is_file(),
            detail=project_dir.as_posix() if pubspec.is_file() else "pubspec.yaml not found",
        )
    )

    manifest_path = resolve_manifest_path(project_dir)
    checks.append(
        DoctorCheck(
            name="screens.yaml",
            ok=manifest_path.is_file(),
            detail=manifest_path.as_posix()
            if manifest_path.is_file()
            else "batch manifest missing",
        )
    )

    config_path = resolve_agent_config_path()
    checks.append(
        DoctorCheck(
            name="agent config (.ai-figma-flutter.yml)",
            ok=config_path.is_file(),
            detail=config_path.as_posix(),
        )
    )

    env_project = settings.default_project_dir
    if env_project:
        checks.append(
            DoctorCheck(
                name="FIGMA_FLUTTER_PROJECT_DIR",
                ok=Path(env_project).expanduser().is_dir(),
                detail=str(env_project),
            )
        )

    for row in collect_font_audit_rows(project_dir):
        checks.append(DoctorCheck(name=row.name, ok=row.ok, detail=row.detail))

    return DoctorReport(checks=tuple(checks))


def format_doctor_report(report: DoctorReport) -> str:
    """Render doctor checks for the wizard."""
    lines: list[str] = []
    for item in report.checks:
        status = "OK" if item.ok else "FAIL"
        lines.append(f"  [{status}] {item.name}: {item.detail}")
    summary = "All checks passed." if report.passed else "Some checks failed."
    return summary + "\n" + "\n".join(lines)
