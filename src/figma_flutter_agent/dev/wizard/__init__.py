"""Interactive wizard workflows: preflight, doctor, sync-preview, Flutter helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.wizard.devices import (
    default_flutter_device_option,
    device_id_from_choice,
    list_flutter_devices,
    resolve_flutter_device_id,
    resolve_flutter_device_id_from_settings,
)
from figma_flutter_agent.dev.wizard.doctor import collect_doctor_report, format_doctor_report
from figma_flutter_agent.dev.wizard.models import DoctorCheck, DoctorReport, ScreenPreflight
from figma_flutter_agent.dev.wizard.preflight import (
    build_run_plan,
    collect_screen_preflight,
    format_screen_preflight,
)
from figma_flutter_agent.dev.wizard.sync import (
    finalize_sync_live_flag,
    generate_screen_for_preview,
    resolve_live_sync,
    run_flutter_analyze,
    sync_preview_workflow,
)

AGENT_REPO_ROOT = Path(__file__).resolve().parents[4]


def agent_repo_root() -> Path:
    """Return the figma-flutter-agent repository root."""
    return AGENT_REPO_ROOT
