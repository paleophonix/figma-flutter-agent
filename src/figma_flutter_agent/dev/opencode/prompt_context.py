"""Orchestrator-injected debug artifacts for OpenRouter read steps."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.run_gate import RUN_MANIFEST_JSON

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
        if name == "last.log":
            content = _read_log_tail(path)
        else:
            content = _read_bounded_text(path)
        if content:
            sections.append(_format_section(name, content))
    return sections


def _cap_prompt(text: str) -> str:
    if len(text) <= _MAX_TOTAL_PROMPT_CHARS:
        return text
    return text[:_MAX_TOTAL_PROMPT_CHARS] + "\n\n[truncated by orchestrator]"


def _resolve_artifact_path(
    worktree: Path,
    debug_mirror: Path,
    ref: str,
) -> Path | None:
    token = ref.strip().replace("\\", "/")
    if not token:
        return None
    candidates = [
        worktree / token,
        debug_mirror / token,
        debug_mirror / Path(token).name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _collect_artifact_ref_sections(
    chain: ReasoningChain,
    *,
    worktree: Path,
    debug_mirror: Path,
) -> list[str]:
    inspect = chain.steps.get("inspect")
    if not isinstance(inspect, dict):
        return []
    refs: list[str] = []
    for entity in inspect.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        for ref in entity.get("artifactRefs") or []:
            text = str(ref).strip()
            if text and text not in refs:
                refs.append(text)
    sections: list[str] = []
    for ref in refs[:12]:
        path = _resolve_artifact_path(worktree, debug_mirror, ref)
        if path is None:
            continue
        content = _read_bounded_text(path)
        if content:
            sections.append(_format_section(ref, content))
    return sections


def build_read_step_user_prompt(
    step: DebugPipelineStep,
    *,
    feature: str,
    board: str,
    worktree: Path,
    debug_mirror: Path,
    chain: ReasoningChain,
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
        parts.append(_format_section("reasoning_chain.recognise", json.dumps(
            chain.steps.get("recognise", {}),
            ensure_ascii=False,
            indent=2,
        )))
        if board == "forensic":
            parts.append("## Forensic artifact excerpts (injected)\n")
            parts.extend(_mirror_file_sections(debug_mirror, _FORENSIC_MIRROR_FILES))
    elif step in {"diagnose", "plan"}:
        parts.append("## Prior reasoning_chain (injected)\n")
        parts.append(_format_section("reasoning_chain", chain.compact_json()))
        if step == "plan":
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
        if board == "forensic":
            parts.append("## Inspect artifactRefs (injected)\n")
            parts.extend(
                _collect_artifact_ref_sections(
                    chain,
                    worktree=worktree,
                    debug_mirror=debug_mirror,
                )
            )
            if step == "diagnose":
                parts.append("## Forensic artifact excerpts (injected)\n")
                parts.extend(_mirror_file_sections(debug_mirror, ("dart-errors.json", "last.log")))
    elif step == "review":
        parts.append("## Prior reasoning_chain (injected)\n")
        parts.append(_format_section("reasoning_chain", chain.compact_json()))

    return _cap_prompt("\n".join(part for part in parts if part is not None))
