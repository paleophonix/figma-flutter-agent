"""Persistent repair pipeline traces (disk + PostHog correlation)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.config.debug_pipeline import DebugPipelineTraceConfig
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.debug.paths import screen_debug_safe_project
from figma_flutter_agent.observability import new_run_id
from figma_flutter_agent.observability.llm_trace import (
    bind_pipeline_observability,
    clear_pipeline_observability,
)
from figma_flutter_agent.observability.posthog_llm import capture_ai_generation

TraceStepStatus = Literal["ok", "blocked", "error", "skipped"]
PromptStoreMode = Literal["off", "hash", "full"]

_TRACE_TIMESTAMP_FMT = "%m%d-%H%M"


def trace_run_folder_name(*, stamp: str, trace_id: str) -> str:
    """Return ``MMDD-HHMM-<run_id>`` directory name for one repair trace."""
    return f"{stamp}-{trace_id}"


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class RepairTraceRecorder:
    """Write one repair run to ``.traces/<project>/<feature>/<MMDD-HHMM>-<run_id>/``."""

    trace_id: str
    root_dir: Path
    steps_dir: Path
    config: DebugPipelineTraceConfig
    settings: Settings
    _seq: int = 0
    _started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _posthog_bound: bool = False

    @classmethod
    def maybe_start(
        cls,
        *,
        settings: Settings,
        project_dir: Path,
        feature: str,
        command: str = "wizard_debug",
        extra_manifest: dict[str, Any] | None = None,
    ) -> RepairTraceRecorder | None:
        """Create trace directory and bind PostHog when enabled."""
        trace_cfg = settings.agent.debug_pipeline.trace
        if not trace_cfg.enabled:
            return None
        trace_id = new_run_id()
        project = screen_debug_safe_project(project_dir)
        stamp = datetime.now(UTC).strftime(_TRACE_TIMESTAMP_FMT)
        root = (
            agent_repo_root()
            / trace_cfg.disk_dir.strip("/\\")
            / project
            / feature
            / trace_run_folder_name(stamp=stamp, trace_id=trace_id)
        )
        steps_dir = root / "steps"
        steps_dir.mkdir(parents=True, exist_ok=True)
        recorder = cls(
            trace_id=trace_id,
            root_dir=root,
            steps_dir=steps_dir,
            config=trace_cfg,
            settings=settings,
        )
        manifest: dict[str, Any] = {
            "trace_id": trace_id,
            "project": project,
            "feature": feature,
            "command": command,
            "started_at": recorder._started_at,
            "folder_stamp": stamp,
            "posthog_trace_id": trace_id,
            "debug_root": f".debug/{project}/{feature}",
        }
        if extra_manifest:
            manifest.update(extra_manifest)
        _write_json(root / "manifest.json", manifest)
        if trace_cfg.posthog:
            bind_pipeline_observability(run_id=trace_id, settings=settings)
            recorder._posthog_bound = True
        return recorder

    def _next_prefix(self, step: str) -> str:
        prefix = f"{self._seq:02d}-{step}"
        self._seq += 1
        return prefix

    def _write_prompts(
        self,
        step_dir: Path,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any] | None:
        mode = self.config.store_prompts
        if mode == "off":
            return None
        if mode == "hash":
            return {
                "system_sha256_16": _digest_text(system_prompt),
                "user_sha256_16": _digest_text(user_prompt),
                "system_chars": len(system_prompt),
                "user_chars": len(user_prompt),
            }
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "prompt.system.txt").write_text(system_prompt, encoding="utf-8")
        (step_dir / "prompt.user.txt").write_text(user_prompt, encoding="utf-8")
        return {
            "system_chars": len(system_prompt),
            "user_chars": len(user_prompt),
            "stored": "full",
        }

    def _copy_panel(self, step_dir: Path, panel_src: Path | None) -> None:
        if panel_src is None or not panel_src.is_dir():
            return
        dest = step_dir / "panel"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(panel_src, dest)

    def record_step(
        self,
        step: str,
        output: dict[str, Any],
        *,
        status: TraceStepStatus = "ok",
        duration_ms: float | None = None,
        meta: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        panel_src: Path | None = None,
        error: str | None = None,
    ) -> None:
        """Persist one pipeline step under ``steps/``."""
        if not self.config.disk:
            return
        prefix = self._next_prefix(step)
        step_dir = self.steps_dir / prefix
        step_dir.mkdir(parents=True, exist_ok=True)
        meta_payload: dict[str, Any] = {
            "step": step,
            "status": status,
            "trace_id": self.trace_id,
        }
        if duration_ms is not None:
            meta_payload["duration_ms"] = round(duration_ms, 1)
        if error:
            meta_payload["error"] = error[:4000]
        if meta:
            meta_payload.update(meta)
        _write_json(step_dir / "meta.json", meta_payload)
        _write_json(step_dir / "output.json", output)
        if system_prompt is not None and user_prompt is not None:
            prompt_meta = self._write_prompts(
                step_dir,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            if prompt_meta is not None:
                _write_json(step_dir / "prompt.json", prompt_meta)
        self._copy_panel(step_dir, panel_src)

    def record_opencode(
        self,
        step: str,
        *,
        output: dict[str, Any],
        response: dict[str, Any],
        duration_ms: float,
        meta: dict[str, Any],
        user_prompt: str,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Persist OpenCode repair/fix step and optional PostHog span."""
        prefix = self._next_prefix(step)
        if self.config.disk:
            step_dir = self.steps_dir / prefix
            step_dir.mkdir(parents=True, exist_ok=True)
            meta_payload: dict[str, Any] = {
                "step": step,
                "status": "error" if is_error else "ok",
                "trace_id": self.trace_id,
                "duration_ms": round(duration_ms, 1),
                "engine": "opencode",
            }
            meta_payload.update(meta)
            if error_message:
                meta_payload["error"] = error_message[:4000]
            _write_json(step_dir / "meta.json", meta_payload)
            _write_json(step_dir / "output.json", output)
            _write_json(
                step_dir / "opencode.json",
                {
                    "response": response,
                    "user_prompt_chars": len(user_prompt),
                },
            )
            prompt_meta = self._write_prompts(
                step_dir,
                system_prompt="",
                user_prompt=user_prompt,
            )
            if prompt_meta is not None:
                _write_json(step_dir / "prompt.json", prompt_meta)
        if self.config.posthog:
            model = str(meta.get("model") or "unknown")
            text_parts: list[str] = []
            for part in response.get("parts") or []:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text") or ""))
            capture_ai_generation(
                settings=self.settings,
                trace_id=self.trace_id,
                span_name=f"repair.{step}",
                provider="openrouter",
                model=model.removeprefix("openrouter/"),
                latency_sec=duration_ms / 1000.0,
                system_prompt="",
                user_prompt=user_prompt,
                output_text="\n".join(text_parts) if text_parts else None,
                is_error=is_error,
                error_message=error_message,
            )

    def finish(
        self,
        *,
        outcome: dict[str, Any],
        chain: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write ``outcome.json``, optional ``chain.json``, and clear PostHog bind."""
        if self.config.disk:
            _write_json(
                self.root_dir / "outcome.json",
                {
                    **outcome,
                    "trace_id": self.trace_id,
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
            if chain is not None:
                _write_json(self.root_dir / "chain.json", {"steps": chain})
        if self._posthog_bound:
            clear_pipeline_observability()
