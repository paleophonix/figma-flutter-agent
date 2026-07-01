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
from figma_flutter_agent.debug.paths import (
    agent_trace_root,
    screen_debug_safe_project,
    screen_root,
)
from figma_flutter_agent.dev.opencode.repair_log import log_repair_step
from figma_flutter_agent.observability import new_run_id
from figma_flutter_agent.observability.llm_trace import pipeline_root_span_id
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


def _trace_debug_root(project_dir: Path, feature: str) -> str:
    """Return a stable trace debug-root path for both repo-local and temp test projects."""
    debug_root = screen_root(project_dir, feature)
    try:
        return debug_root.relative_to(agent_repo_root()).as_posix()
    except ValueError:
        return debug_root.as_posix()


@dataclass
class RepairTraceRecorder:
    """Write one repair run to ``.debug/agent/<project>/<feature>/trace/`` (overwrite)."""

    trace_id: str
    root_dir: Path
    steps_dir: Path
    config: DebugPipelineTraceConfig
    settings: Settings
    feature: str = ""
    project: str = ""
    command: str = "wizard_debug"
    _seq: int = 0
    _started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _total_tokens_in: int = 0
    _total_tokens_out: int = 0
    _total_cost_usd: float = 0.0
    _step_stats: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def maybe_start(
        cls,
        *,
        settings: Settings,
        project_dir: Path,
        feature: str,
        command: str = "wizard_debug",
        trace_id: str | None = None,
        extra_manifest: dict[str, Any] | None = None,
    ) -> RepairTraceRecorder | None:
        """Create trace directory and bind PostHog when enabled."""
        trace_cfg = settings.agent.debug_pipeline.trace
        if not trace_cfg.enabled:
            return None
        resolved_trace_id = trace_id or new_run_id()
        project = screen_debug_safe_project(project_dir)
        stamp = datetime.now(UTC).strftime(_TRACE_TIMESTAMP_FMT)
        root = agent_trace_root(project_dir, feature)
        if root.exists():
            shutil.rmtree(root)
        steps_dir = root / "steps"
        steps_dir.mkdir(parents=True, exist_ok=True)
        recorder = cls(
            trace_id=resolved_trace_id,
            root_dir=root,
            steps_dir=steps_dir,
            config=trace_cfg,
            settings=settings,
            feature=feature,
            project=project,
            command=command,
        )
        manifest: dict[str, Any] = {
            "trace_id": resolved_trace_id,
            "project": project,
            "feature": feature,
            "command": command,
            "started_at": recorder._started_at,
            "folder_stamp": stamp,
            "posthog_trace_id": resolved_trace_id,
            "debug_root": _trace_debug_root(project_dir, feature),
        }
        if extra_manifest:
            manifest.update(extra_manifest)
        _write_json(root / "manifest.json", manifest)
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

    def _accumulate_step_stats(
        self,
        step: str,
        *,
        status: TraceStepStatus | str,
        duration_ms: float | None,
        meta: dict[str, Any] | None,
        engine: str = "openrouter",
    ) -> None:
        """Track rollup counters for finish metadata and PostHog aggregation."""
        tokens_in = (meta or {}).get("tokens_in")
        tokens_out = (meta or {}).get("tokens_out")
        cost_usd = (meta or {}).get("cost_usd")
        if isinstance(tokens_in, int):
            self._total_tokens_in += tokens_in
        if isinstance(tokens_out, int):
            self._total_tokens_out += tokens_out
        if isinstance(cost_usd, (int, float)):
            self._total_cost_usd += float(cost_usd)
        self._step_stats.append(
            {
                "step": step,
                "status": status,
                "engine": (meta or {}).get("engine") or engine,
                "model": (meta or {}).get("model"),
                "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
            }
        )

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
        log_repair_step(
            step,
            status=status,
            duration_ms=duration_ms,
            trace_id=self.trace_id,
            **(meta or {}),
        )
        self._accumulate_step_stats(
            step,
            status=status,
            duration_ms=duration_ms,
            meta=meta,
        )
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
        log_repair_step(
            step,
            status="error" if is_error else "ok",
            duration_ms=duration_ms,
            trace_id=self.trace_id,
            engine="opencode",
            **meta,
        )
        self._accumulate_step_stats(
            step,
            status="error" if is_error else "ok",
            duration_ms=duration_ms,
            meta=meta,
            engine="opencode",
        )
        if not self.config.disk:
            return
        prefix = self._next_prefix(step)
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

    def _pipeline_latency_sec(self) -> float:
        started = datetime.fromisoformat(self._started_at)
        return max((datetime.now(UTC) - started).total_seconds(), 0.0)

    def _resolve_aggregated_model(self) -> str:
        models = {
            str(item["model"]).removeprefix("openrouter/")
            for item in self._step_stats
            if item.get("model")
        }
        if len(models) == 1:
            return next(iter(models))
        if not models:
            return "unknown"
        return "mixed"

    def _emit_aggregated_posthog(self, *, outcome: dict[str, Any], rollup: dict[str, Any]) -> None:
        """Send one PostHog rollup for the full repair pipeline (RepairPosthogAggregateLaw)."""
        if not self.config.posthog:
            return
        if not self.settings.posthog_api_key.get_secret_value():
            return
        latency_sec = self._pipeline_latency_sec()
        stopped = bool(outcome.get("stopped"))
        span_name = f"repair.{self.feature or 'pipeline'}"
        root_span_id = pipeline_root_span_id(self.trace_id)
        capture_ai_generation(
            settings=self.settings,
            trace_id=self.trace_id,
            span_name=span_name,
            provider="openrouter",
            model=self._resolve_aggregated_model(),
            latency_sec=latency_sec,
            system_prompt="",
            user_prompt=json.dumps({"steps": self._step_stats}, ensure_ascii=False),
            output_text=json.dumps(outcome, ensure_ascii=False),
            is_error=stopped,
            error_message=str(outcome.get("stop_reason")) if stopped else None,
            input_tokens=rollup.get("tokens_in_total") or None,
            output_tokens=rollup.get("tokens_out_total") or None,
            total_cost_usd=rollup.get("cost_usd_total") or None,
            parent_span_id=root_span_id,
            span_id=root_span_id,
            extra_properties={
                "feature": self.feature,
                "project": self.project,
                "command": self.command,
                "pipeline": "repair",
                "repair_step_count": rollup.get("step_count"),
                "repair_steps": self._step_stats,
                "stop_reason": outcome.get("stop_reason"),
            },
        )

    def finish(
        self,
        *,
        outcome: dict[str, Any],
        chain: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write ``outcome.json``, optional ``chain.json``, and aggregated PostHog rollup."""
        rollup = self._build_rollup(outcome)
        if self.config.disk:
            _write_json(
                self.root_dir / "outcome.json",
                {
                    **outcome,
                    "trace_id": self.trace_id,
                    "finished_at": datetime.now(UTC).isoformat(),
                    "rollup": rollup,
                },
            )
            if chain is not None:
                _write_json(self.root_dir / "chain.json", {"steps": chain})
        self._emit_aggregated_posthog(outcome=outcome, rollup=rollup)
        log_repair_step(
            "finish",
            status="ok" if not outcome.get("stopped") else "blocked",
            trace_id=self.trace_id,
            **{
                k: v
                for k, v in outcome.items()
                if k in {"stop_reason", "loop_rounds", "gate_verdict"}
            },
        )

    def _build_rollup(self, outcome: dict[str, Any]) -> dict[str, Any]:
        """Aggregate per-step latency and token usage."""
        outlier_step = None
        outlier_ms = -1.0
        for item in self._step_stats:
            duration = item.get("duration_ms")
            if isinstance(duration, (int, float)) and duration > outlier_ms:
                outlier_ms = float(duration)
                outlier_step = item.get("step")
        completed = not outcome.get("stopped", False)
        return {
            "tokens_in_total": self._total_tokens_in,
            "tokens_out_total": self._total_tokens_out,
            "cost_usd_total": round(self._total_cost_usd, 8) if self._total_cost_usd else 0.0,
            "step_count": len(self._step_stats),
            "outlier_step": outlier_step,
            "outlier_duration_ms": outlier_ms if outlier_ms >= 0 else None,
            "loop_rounds": outcome.get("loop_rounds"),
            "cost_per_completed_case": {
                "tokens_in": self._total_tokens_in if completed else None,
                "tokens_out": self._total_tokens_out if completed else None,
                "cost_usd": round(self._total_cost_usd, 8)
                if completed and self._total_cost_usd
                else None,
            },
        }
