"""Environment checks for figma-flutter development."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config import Settings, agent_repo_root, resolve_agent_config_path
from figma_flutter_agent.dev.ast_sidecar_build import ast_sidecar_preflight
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable, resolve_flutter_executable
from figma_flutter_agent.dev.golden_capture_build import (
    GOLDEN_CAPTURE_IMAGE,
    golden_capture_image_present,
)
from figma_flutter_agent.fonts.diagnostics import audit_assets_fonts
from figma_flutter_agent.observability.loki_sink import normalize_loki_push_url
from figma_flutter_agent.tools.ast_sidecar.commands import (
    compiler_invocation,
    prebuilt_compiler_path,
)
from figma_flutter_agent.validation.golden_runtime import docker_cli_available, golden_compose_file


@dataclass(frozen=True)
class DoctorCheck:
    """Single doctor check row."""

    name: str
    ok: bool
    detail: str


def run_doctor(
    *, settings: Settings | None = None, project_dir: Path | None = None
) -> list[DoctorCheck]:
    """Run local environment checks.

    Args:
        settings: Optional pre-loaded settings.
        project_dir: Optional Flutter project root for project-specific checks.

    Returns:
        List of check results.
    """
    rows: list[DoctorCheck] = []
    root = agent_repo_root()
    resolved = settings or Settings()

    if project_dir is not None:
        assets_row = audit_assets_fonts(project_dir)
        rows.append(
            DoctorCheck(
                name=assets_row.name,
                ok=assets_row.ok,
                detail=assets_row.detail,
            )
        )

    poetry = shutil.which("poetry")
    rows.append(
        DoctorCheck(
            name="poetry",
            ok=poetry is not None,
            detail=poetry or "not on PATH",
        )
    )

    sdk_root = resolved.flutter_sdk or None
    flutter = resolve_flutter_executable(sdk_root=sdk_root)
    rows.append(
        DoctorCheck(
            name="flutter",
            ok=flutter is not None,
            detail=flutter or "not on PATH (set FIGMA_FLUTTER_SDK)",
        )
    )

    dart = resolve_dart_executable(sdk_root=sdk_root)
    rows.append(
        DoctorCheck(
            name="dart",
            ok=dart is not None,
            detail=dart or "not on PATH",
        )
    )

    prebuilt = prebuilt_compiler_path()
    ast_preflight = ast_sidecar_preflight(resolved)
    compiler = compiler_invocation()
    if prebuilt is not None:
        ast_ok = True
        ast_detail = str(prebuilt)
    elif ast_preflight is not None:
        script = ast_preflight.build_script.name
        if ast_preflight.can_build:
            ast_ok = False
            ast_detail = (
                f"prebuilt missing ({ast_preflight.expected_binary.name}); "
                f"run tools/{script} or figma-flutter doctor --build-ast"
            )
        else:
            ast_ok = False
            ast_detail = (
                f"prebuilt missing; Dart unavailable — set FIGMA_FLUTTER_SDK, then tools/{script}"
            )
    elif compiler is not None:
        ast_ok = True
        ast_detail = f"fallback: {' '.join(compiler)}"
    else:
        ast_ok = False
        ast_detail = "missing — set FIGMA_FLUTTER_SDK and run tools/build_sidecars.*"
    rows.append(DoctorCheck(name="ast_sidecar", ok=ast_ok, detail=ast_detail))

    docker_ok = docker_cli_available()
    compose = golden_compose_file()
    rows.append(
        DoctorCheck(
            name="docker",
            ok=docker_ok,
            detail="available (recommended for golden CI)" if docker_ok else "not available — host golden only",
        )
    )
    rows.append(
        DoctorCheck(
            name="golden_compose",
            ok=compose.is_file(),
            detail=str(compose) if compose.is_file() else "missing tools/render-capture/docker-compose.yml",
        )
    )
    if not docker_ok:
        golden_image_ok = True
        golden_image_detail = "skipped (Docker unavailable; use runtime.golden_capture: host)"
    elif golden_capture_image_present():
        golden_image_ok = True
        golden_image_detail = GOLDEN_CAPTURE_IMAGE
    else:
        golden_image_ok = False
        golden_image_detail = (
            f"missing {GOLDEN_CAPTURE_IMAGE} — "
            "auto-build on golden capture, or doctor --build-golden"
        )
    rows.append(
        DoctorCheck(
            name="golden_image",
            ok=golden_image_ok,
            detail=golden_image_detail,
        )
    )

    config_path = root / ".ai-figma-flutter.yml"
    if settings is None:
        try:
            resolve_agent_config_path()
            config_ok = True
            config_detail = str(config_path if config_path.is_file() else root / ".ai-figma-flutter.yml.example")
        except Exception as exc:
            config_ok = False
            config_detail = str(exc)
    else:
        config_ok = True
        config_detail = str(getattr(settings, "config_path", None) or config_path)

    rows.append(DoctorCheck(name="agent_config", ok=config_ok, detail=config_detail))

    flutter_version_file = root / ".flutter-version"
    rows.append(
        DoctorCheck(
            name="flutter_version_pin",
            ok=flutter_version_file.is_file(),
            detail=flutter_version_file.read_text(encoding="utf-8").strip()
            if flutter_version_file.is_file()
            else "missing .flutter-version",
        )
    )

    rows.append(
        DoctorCheck(
            name="python",
            ok=True,
            detail=sys.version.split()[0],
        )
    )

    provider = resolved.resolved_llm_provider()
    llm_key = resolved.llm_api_key()
    rows.append(
        DoctorCheck(
            name="llm_provider",
            ok=True,
            detail=f"{provider} ({resolved.llm_api_key_env_name()})",
        )
    )
    rows.append(
        DoctorCheck(
            name="llm_api_key",
            ok=bool(llm_key.strip()),
            detail="set" if llm_key.strip() else f"missing {resolved.llm_api_key_env_name()}",
        )
    )
    rows.append(_loki_observability_check(resolved))
    rows.append(_preview_capture_check(flutter is not None))
    rows.extend(_fidelity_engine_checks(resolved))
    return rows


def _preview_capture_check(flutter_ok: bool) -> DoctorCheck:
    """Report Flutter warm-sandbox availability for preview capture (chrome parity)."""
    if not flutter_ok:
        return DoctorCheck(
            name="preview_capture",
            ok=False,
            detail="requires Flutter SDK (preview mode uses flutter test warm sandbox)",
        )
    return DoctorCheck(
        name="preview_capture",
        ok=True,
        detail="flutter warm sandbox (chrome-parity PNG; sketch CLI: preview-capture --layout-json)",
    )


def _loki_observability_check(settings: Settings) -> DoctorCheck:
    """Report whether Grafana Loki remote log shipping is configured."""
    if not settings.loki_enabled:
        return DoctorCheck(
            name="loki_logs",
            ok=True,
            detail="disabled (LOKI_ENABLED=false)",
        )
    if not normalize_loki_push_url(settings.loki_url):
        return DoctorCheck(
            name="loki_logs",
            ok=True,
            detail="disabled (set LOKI_URL to ship logs)",
        )
    host = normalize_loki_push_url(settings.loki_url).split("://", 1)[-1].split("/", 1)[0]
    auth = "basic" if settings.loki_user.strip() else "bearer" if settings.loki_api_key.get_secret_value().strip() else "none"
    return DoctorCheck(
        name="loki_logs",
        ok=True,
        detail=f"enabled -> {host} (auth={auth})",
    )


def _fidelity_engine_checks(settings: Settings) -> list[DoctorCheck]:
    """Report Fidelity Engine v2 settings (geometry gate, IR, refine)."""
    from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest

    generation = settings.agent.generation
    manifest = load_screens_manifest()
    screen_count = len(manifest.screens)
    return [
        DoctorCheck(
            name="fidelity_geometry_gate",
            ok=generation.runtime_geometry_gate,
            detail=(
                f"gate={generation.runtime_geometry_gate}, "
                f"tiers={generation.runtime_geometry_use_tier_thresholds}, "
                f"capture_if_missing={generation.runtime_geometry_capture_if_missing}"
            ),
        ),
        DoctorCheck(
            name="fidelity_screen_ir",
            ok=generation.use_screen_ir,
            detail=(
                f"use_screen_ir={generation.use_screen_ir}, "
                f"require_screen_ir={generation.require_screen_ir}"
            ),
        ),
        DoctorCheck(
            name="fidelity_visual_refine",
            ok=not generation.llm_visual_refine or generation.runtime_geometry_gate,
            detail=(
                f"llm_visual_refine={generation.llm_visual_refine} "
                f"(set true via apply_refine_ready_profile after baseline is green)"
            ),
        ),
        DoctorCheck(
            name="fidelity_fixture_screens",
            ok=screen_count > 0,
            detail=f"{screen_count} manifest screens — signoff runs geometry on all unless FIGMA_GEOMETRY_SIGNOFF_SCREENS is set",
        ),
    ]
