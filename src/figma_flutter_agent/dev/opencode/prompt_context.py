"""Orchestrator-injected debug artifacts for OpenRouter read steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.dev.opencode.chain_compact import compact_recognise
from figma_flutter_agent.dev.opencode.prompt_assembler import assemble_step_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repair_prompt import cap_repair_write_prompt
from figma_flutter_agent.dev.opencode.run_gate import RUN_MANIFEST_JSON

_PLAN_RUN_FACT_FILES: tuple[str, ...] = (RUN_MANIFEST_JSON, "capture.json")
_PLAN_RUN_FACT_MAX_BYTES = 6_000

_FORENSIC_MIRROR_FILES: tuple[str, ...] = (
    RUN_MANIFEST_JSON,
    "dart-errors.json",
    "last.log",
    "capture.json",
    "run.meta.json",
)

_SCREEN_MIRROR_FILES: tuple[str, ...] = (
    RUN_MANIFEST_JSON,
    "dart-errors.json",
    "last.log",
    "capture.json",
    "semantics.json",
)

_MAX_FILE_BYTES = 24_000
_MAX_LOG_TAIL_BYTES = 16_000
_MAX_TOTAL_PROMPT_CHARS = 96_000


def _read_bounded_text(path: Path, *, max_bytes: int = _MAX_FILE_BYTES) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace").strip()


def _read_log_tail(path: Path, *, max_bytes: int = _MAX_LOG_TAIL_BYTES) -> str:
    return _read_bounded_text(path, max_bytes=max_bytes)


def _format_section(title: str, body: str) -> str:
    return f"### {title}\n```\n{body}\n```\n"


def _mirror_file_sections(debug_mirror: Path, names: tuple[str, ...]) -> list[str]:
    sections: list[str] = []
    for name in names:
        path = debug_mirror / name
        if not path.is_file():
            continue
        content = _read_log_tail(path) if name == "last.log" else _read_bounded_text(path)
        if content:
            sections.append(_format_section(name, content))
    return sections


def _cap_prompt(text: str) -> str:
    if len(text) <= _MAX_TOTAL_PROMPT_CHARS:
        return text
    return text[:_MAX_TOTAL_PROMPT_CHARS] + "\n\n[truncated by orchestrator]"


def build_read_step_user_prompt(
    step: DebugPipelineStep,
    *,
    feature: str,
    board: str,
    worktree: Path,
    debug_mirror: Path,
    chain: ReasoningChain,
    run_context: dict[str, Any] | None = None,
) -> str:
    """Build user prompt with orchestrator-injected artifact excerpts.

    Args:
        step: Pipeline read step name.
        feature: Screen feature slug.
        board: Agent board (``screen`` or ``forensic``).
        worktree: Repair git worktree root.
        debug_mirror: Copied debug bundle under ``.repair/debug/``.
        chain: Cumulative reasoning chain for prior executive JSON.

    Returns:
        User message text for OpenRouter structured read steps.
    """
    mirror_rel = debug_mirror.relative_to(worktree).as_posix()
    parts = [
        f"Repair case for feature {feature}.",
        f"Debug mirror path (relative to worktree): {mirror_rel}",
        "",
        "The orchestrator injected artifact excerpts below. "
        "Treat them as primary evidence; do not claim files are missing when present here.",
        "",
    ]

    if step == "recognise":
        parts.append("## Hot triage bundle (injected)\n")
        names = _FORENSIC_MIRROR_FILES if board == "forensic" else _SCREEN_MIRROR_FILES
        parts.extend(_mirror_file_sections(debug_mirror, names))
    elif step == "inspect":
        parts.append("## Prior recognise output\n")
        recognise = chain.steps.get("recognise")
        if isinstance(recognise, dict):
            parts.append(
                _format_section(
                    "recognise",
                    json.dumps(compact_recognise(recognise), ensure_ascii=False, indent=2),
                )
            )
        if board == "forensic":
            parts.append("## Forensic artifact excerpts (injected)\n")
            parts.extend(_mirror_file_sections(debug_mirror, _FORENSIC_MIRROR_FILES))
    elif step == "diagnose":
        recognise = chain.steps.get("recognise")
        if isinstance(recognise, dict) and recognise.get("blocked"):
            parts.append(
                "## Forensic compiler note (injected)\n"
                "recognise.blocked=true does NOT permit empty diagnose.laws[] when "
                "inspect.entities include src/figma_flutter_agent repoPaths. "
                "Emit P0 compiler laws for PATCH_RUNTIME / emitter surfaces.\n"
            )
        validation_error = (run_context or {}).get("diagnose_validation_error")
        if validation_error:
            parts.append("## Prior diagnose validation error (must fix on this retry)\n")
            parts.append(_format_section("diagnose_validation_error", str(validation_error)))
        if board == "forensic":
            parts.append("## Forensic artifact excerpts (injected)\n")
            parts.extend(_mirror_file_sections(debug_mirror, ("dart-errors.json", "last.log")))
    elif step == "plan":
        validation_error = (run_context or {}).get("plan_validation_error")
        if validation_error:
            parts.append("## Prior plan validation error (must fix on this retry)\n")
            parts.append(_format_section("plan_validation_error", str(validation_error)))
        pivot = (run_context or {}).get("pivot")
        if isinstance(pivot, dict) and pivot:
            parts.append("## Pivot context (repair/check revise)\n")
            parts.append(
                _format_section(
                    "pivot",
                    json.dumps(pivot, ensure_ascii=False, indent=2),
                )
            )
        parts.append("## Run facts (injected)\n")
        for name in _PLAN_RUN_FACT_FILES:
            path = debug_mirror / name
            if path.is_file():
                parts.append(
                    _format_section(
                        name,
                        _read_bounded_text(path, max_bytes=_PLAN_RUN_FACT_MAX_BYTES),
                    )
                )
        from figma_flutter_agent.dev.opencode.plan_validate import compiler_path_catalog

        catalog = compiler_path_catalog(worktree)
        if catalog:
            parts.append("## Existing compiler paths (plan targetFiles must use these)\n")
            parts.append(
                _format_section(
                    "compiler_path_catalog",
                    "\n".join(catalog[:48]),
                )
            )
    elif step == "review":
        parts.append("## Executive chain summary (injected)\n")
        parts.append(
            _format_section(
                "reasoning_chain",
                json.dumps(chain.compact_for_step("review"), ensure_ascii=False, indent=2),
            )
        )

    return _cap_prompt("\n".join(part for part in parts if part is not None))


def build_write_step_user_prompt(
    step: Literal["repair", "fix"],
    *,
    feature: str,
    board: str,
    worktree: Path,
    debug_mirror: Path,
    chain: ReasoningChain,
    run_context: dict[str, Any],
    l6_bindings: dict[str, str],
    plan: dict[str, Any] | None = None,
) -> str:
    """Build OpenCode user message with full ACDP stack for build-mode steps.

    Read steps use OpenRouter with ``assemble_step_prompt`` as system text. Repair/fix
    embed the same L1-L5 skill stack in the OpenCode user message; L6 is file-first
    for repair (state paths + compact diagnose laws + edit scope).
    """
    plan_step_orders = run_context.get("planStepOrders")
    if not isinstance(plan_step_orders, list):
        plan_step_orders = []
    plan_orders = [int(x) for x in plan_step_orders if isinstance(x, (int, float))]

    if step == "repair":
        acdp = assemble_step_prompt(
            step,
            board=board,
            run_context=run_context,
            reasoning_chain_json="{}",
            l6_bindings=l6_bindings,
        )
    else:
        reasoning = chain.compact_json_for_step(step, run_context.get("pivot"))
        acdp = assemble_step_prompt(
            step,
            board=board,
            run_context=run_context,
            reasoning_chain_json=reasoning,
            l6_bindings=l6_bindings,
        )
    parts = [
        acdp,
        "",
        "## User task",
        "",
        f"Repair case for feature {feature}.",
        f"Worktree: {worktree.as_posix()}",
        f"Debug mirror: {debug_mirror.relative_to(worktree).as_posix()}",
        "",
    ]
    if step == "repair":
        parts.extend(
            [
                "Implement assigned CODE_CHANGE plan steps in this sandbox worktree.",
                "Edit src/figma_flutter_agent/ targetFiles from plan only.",
                "Do not write executive JSON (repair.json); the orchestrator records repair state.",
                "Read at most one plan targetFile before the first compiler edit; "
                "do not re-read .debug artifacts unless a plan test names them.",
                "Do not run exploratory bash loops or re-diagnose — implement the law patch.",
                "",
            ]
        )
        continuation = run_context.get("repair_continuation_summary")
        if isinstance(continuation, str) and continuation.strip():
            parts.extend(
                [
                    "## Continuation (mandatory)",
                    "A prior repair session ended without compiler edits (step budget or noop).",
                    "Do **not** re-run broad repo exploration. Apply the patch described below.",
                    "Use at most one read on each plan targetFile, then edit.",
                    "",
                    _format_section("prior_repair_summary", continuation.strip()),
                    "",
                ]
            )
        if plan_orders:
            parts.append(
                _format_section(
                    "planStepOrders",
                    json.dumps(plan_orders, ensure_ascii=False, indent=2),
                )
            )
        pivot = run_context.get("pivot")
        if isinstance(pivot, dict) and pivot:
            parts.append(
                _format_section(
                    "pivot",
                    json.dumps(pivot, ensure_ascii=False, indent=2),
                )
            )
        return cap_repair_write_prompt(_cap_prompt("\n".join(parts)))
    elif step == "fix":
        parts.extend(
            [
                "Emit-layer fix: patch only .repair/candidate/planned_files per fix skill.",
                "",
            ]
        )
        check_payload = chain.steps.get("check")
        if isinstance(check_payload, dict):
            parts.append(
                _format_section(
                    "check.json",
                    json.dumps(check_payload, ensure_ascii=False, indent=2),
                )
            )
    return _cap_prompt("\n".join(parts))
