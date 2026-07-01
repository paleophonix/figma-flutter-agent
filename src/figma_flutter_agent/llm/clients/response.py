"""Response parsing/validation mixin for LLM clients."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.schema import StructuredOutputSpec  # noqa: F401  (re-export context)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FlutterRepairPatchResponse,
    RepairCpiSupervisorResponse,
)


class ResponseMixin:
    """Response parsing and validation helpers shared across LLM provider clients."""

    def _finalize_generation_response(
        self,
        response: FlutterGenerationResponse,
        *,
        clean_tree: CleanDesignTreeNode,
        use_screen_ir: bool,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
        tokens: DesignTokens | None = None,
        feature_name: str | None = None,
        persist_ir_snapshots: bool = True,
    ) -> FlutterGenerationResponse:
        if response.screen_ir is not None:
            from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
            from figma_flutter_agent.generator.ir.presence import (
                expand_extracted_widget_names_for_validate,
                normalize_screen_ir_presence,
            )
            from figma_flutter_agent.generator.ir.validate import (
                validate_extracted_widgets,
                validate_screen_ir,
            )

            if persist_ir_snapshots and project_dir is not None and feature_name:
                write_screen_ir_snapshot(
                    stage="llm_parsed",
                    feature_name=feature_name,
                    screen_ir=response.screen_ir,
                    extracted_widgets=response.extracted_widgets or None,
                    project_dir=project_dir,
                )

            extracted = frozenset(widget.widget_name for widget in response.extracted_widgets)
            screen_ir = normalize_screen_ir_presence(
                response.screen_ir,
                clean_tree,
                extracted_widget_names=extracted,
            )
            if screen_ir is not response.screen_ir:
                response = response.model_copy(update={"screen_ir": screen_ir})
            extracted_for_validate = expand_extracted_widget_names_for_validate(
                extracted,
                clean_tree=clean_tree,
                screen_ir=screen_ir,
            )
            validate_screen_ir(
                response.screen_ir,
                clean_tree,
                extracted_widget_names=extracted_for_validate,
                declared_extracted_widget_names=extracted,
                project_dir=project_dir,
                tokens=tokens,
                skip_presence_normalize=True,
            )
            validate_extracted_widgets(
                response.extracted_widgets,
                clean_tree,
                project_dir=project_dir,
                tokens=tokens,
            )
            if (
                persist_ir_snapshots
                and project_dir is not None
                and feature_name
                and response.screen_ir is not None
            ):
                write_screen_ir_snapshot(
                    stage="llm_validated",
                    feature_name=feature_name,
                    screen_ir=response.screen_ir,
                    extracted_widgets=response.extracted_widgets or None,
                    project_dir=project_dir,
                )
            return response.model_copy(update={"screen_code": None})
        if response.resolved_screen_code():
            raise LlmError(
                "Model returned screenCode; screenIr is required and Dart screen bodies "
                "are no longer accepted"
            )
        raise LlmError("LLM response missing screenIr")

    def _parse_repair_patch_response(self, raw_text: str) -> FlutterRepairPatchResponse:
        try:
            payload = json.loads(self._coerce_json_text(raw_text))
            return FlutterRepairPatchResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("LLM repair patch validation failed: {}", exc)
            raise LlmError(f"LLM repair patch validation failed: {exc}") from exc

    def _parse_cpi_supervisor_response(self, raw_text: str) -> RepairCpiSupervisorResponse:
        try:
            payload = json.loads(self._coerce_json_text(raw_text))
            return RepairCpiSupervisorResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("CPI supervisor validation failed: {}", exc)
            raise LlmError(f"CPI supervisor validation failed: {exc}") from exc

    @staticmethod
    def _coerce_json_text(raw_text: str) -> str:
        """Strip markdown fences and whitespace from provider JSON payloads."""
        text = raw_text.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _looks_like_truncated_json(self, raw_text: str) -> bool:
        text = self._coerce_json_text(raw_text)
        if not text:
            return True
        if text.count("{") != text.count("}"):
            return True
        if text.count("[") != text.count("]"):
            return True
        return text.rstrip().endswith(",")

    def _parse_generation_response(self, raw_text: str) -> FlutterGenerationResponse:
        coerced = self._coerce_json_text(raw_text)
        if self._looks_like_truncated_json(raw_text):
            raise LlmError(
                "LLM response JSON appears truncated (unbalanced brackets or trailing comma); "
                "increase max output tokens or reduce payload size"
            )
        try:
            payload = json.loads(coerced)
            return FlutterGenerationResponse.model_validate(payload)
        except json.JSONDecodeError as exc:
            logger.warning("LLM structured output JSON parse failed: {}", exc)
            raise LlmError(f"LLM response validation failed: {exc}") from exc
        except ValueError as exc:
            logger.warning("LLM structured output validation failed: {}", exc)
            raise LlmError(f"LLM response validation failed: {exc}") from exc
