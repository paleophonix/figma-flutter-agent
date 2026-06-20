"""Assemble ACDP prompts for OpenCode repair pipeline steps."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.dev.opencode.l6_context import render_l6_template
from figma_flutter_agent.llm.prompts.compose import _compose_acdp_prompt


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _skill_dir(step: str, board: str) -> Path:
    root = agent_repo_root() / ".opencode" / "skills"
    if step in {"recognise", "inspect"}:
        forked = root / f"{step}-{board}"
        if forked.is_dir():
            return forked
    return root / step


def _master_l1(board: str) -> str:
    path = agent_repo_root() / ".opencode" / "prompts" / f"repair-master-{board}.md"
    return _read_text(path)


def _invariants_l3() -> str:
    path = agent_repo_root() / ".opencode" / "prompts" / "repair-invariants.md"
    return _read_text(path)


def _render_l6(
    template: str,
    *,
    run_context: dict,
    reasoning_chain_json: str,
    l6_bindings: dict[str, str] | None = None,
) -> str:
    bindings = dict(l6_bindings or run_context.get("_l6_bindings") or {})
    bindings.setdefault("run_context_json", json.dumps(run_context, ensure_ascii=False, indent=2))
    bindings.setdefault("reasoning_chain_json", reasoning_chain_json)
    return render_l6_template(template, bindings)


def assemble_step_prompt(
    step: str,
    *,
    board: str,
    run_context: dict,
    reasoning_chain_json: str,
    l6_bindings: dict[str, str] | None = None,
) -> str:
    """Build full system prompt for one pipeline step."""
    skill = _skill_dir(step, board)
    l2 = _read_text(skill / "l2-role.md")
    l3_skill = _read_text(skill / "l3-principles.md")
    l4 = _read_text(skill / "l4-capabilities.md")
    l5 = _read_text(skill / "l5-actions.md")
    l6_tpl = _read_text(skill / "l6-environment.tpl")
    l6 = _render_l6(
        l6_tpl,
        run_context=run_context,
        reasoning_chain_json=reasoning_chain_json,
        l6_bindings=l6_bindings,
    )
    return _compose_acdp_prompt(
        l1=_master_l1(board),
        l2=l2,
        l3_core=_invariants_l3(),
        l3_principles_ext=l3_skill,
        l4=l4,
        l5_core=l5,
        l6=l6,
    )
