"""Transactional generated-file writer."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.postprocess import process_generated_dart_source
from figma_flutter_agent.generator.writing.custom_code import (
    find_orphan_line_numbers,
    format_orphan_edit_message,
    merge_custom_code,
)
from figma_flutter_agent.generator.writing.io import atomic_write_text, read_text_file
from figma_flutter_agent.generator.writing.models import WriteBatch, WriteRecord


class DartWriter:
    """Write generated Dart files into a Flutter project."""

    def __init__(
        self,
        project_dir: Path,
        *,
        enable_backup: bool = True,
        strict_preservation: bool = False,
    ) -> None:
        self._project_dir = project_dir
        self._project_dir_resolved = project_dir.resolve()
        self._enable_backup = enable_backup
        self._strict_preservation = strict_preservation
        self._orphan_warnings_emitted: set[str] = set()

    def _finalize_dart_content(self, relative_path: str, content: str) -> str:
        if not relative_path.endswith(".dart"):
            return content
        normalized = relative_path.replace("\\", "/")
        from figma_flutter_agent.generator.dart.file_parts import relocate_directives_to_header
        from figma_flutter_agent.generator.dart.syntax_repairs import apply_llm_dart_syntax_repairs
        from figma_flutter_agent.generator.planned.reconcile import (
            _sanitize_ingested_widget_source,
            _skips_codegen_ast_pass,
        )

        if normalized.startswith("lib/widgets/"):
            return _sanitize_ingested_widget_source(content, widget_path=normalized)
        if normalized.startswith("test/capture/"):
            from figma_flutter_agent.generator.capture_screen_test import (
                finalize_capture_screen_test_content,
            )

            return finalize_capture_screen_test_content(content)
        if _skips_codegen_ast_pass(normalized, content):
            return relocate_directives_to_header(apply_llm_dart_syntax_repairs(content))
        return process_generated_dart_source(content)

    def _safe_target_path(self, relative_path: str) -> Path:
        candidate = (self._project_dir / relative_path).resolve()
        if not candidate.is_relative_to(self._project_dir_resolved):
            raise GenerationError(f"Refusing to write outside project directory: {relative_path}")
        return candidate

    def write_files(self, files: dict[str, str]) -> WriteBatch | None:
        """Write generated files and return a batch that must be committed or rolled back."""
        self._orphan_warnings_emitted.clear()
        orphan_reports: list[tuple[str, str, list[int]]] = []

        def stage_file(relative_path: str, content: str) -> str:
            target = self._safe_target_path(relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            content_to_write = content
            normalized_path = relative_path.replace("\\", "/")
            if target.exists() and not normalized_path.startswith("test/"):
                existing_content = read_text_file(target)
                orphan_lines = find_orphan_line_numbers(existing_content)
                if orphan_lines:
                    orphan_reports.append((relative_path, existing_content, orphan_lines))
                content_to_write = merge_custom_code(content, existing_content)
            return self._finalize_dart_content(relative_path, content_to_write)

        if not self._enable_backup:
            for relative_path, content in files.items():
                target = self._safe_target_path(relative_path)
                atomic_write_text(target, stage_file(relative_path, content))
            self._emit_orphan_warnings(orphan_reports)
            return None

        backup_dir = Path(tempfile.mkdtemp(prefix="figma-flutter-backup-"))
        written: list[WriteRecord] = []
        try:
            for relative_path, content in files.items():
                target = self._safe_target_path(relative_path)
                existed_before = target.exists()
                if existed_before:
                    backup_target = backup_dir / relative_path
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_target)

                atomic_write_text(target, stage_file(relative_path, content))
                written.append(WriteRecord(target=target, existed_before=existed_before))
        except OSError as exc:
            logger.error("Writing failed, executing rollback...")
            self._restore_backup(backup_dir, written)
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise GenerationError(f"Failed to write generated files: {exc}") from exc

        self._emit_orphan_warnings(orphan_reports)
        return WriteBatch(backup_dir=backup_dir, written=written)

    def commit_batch(self, batch: WriteBatch | None) -> None:
        """Delete backup artifacts after validation succeeds."""
        if batch is None:
            return
        shutil.rmtree(batch.backup_dir, ignore_errors=True)

    def rollback_batch(self, batch: WriteBatch | None) -> None:
        """Restore files from backup after validation or pubspec merge failure."""
        if batch is None:
            return
        self._restore_backup(batch.backup_dir, batch.written)
        shutil.rmtree(batch.backup_dir, ignore_errors=True)

    def _emit_orphan_warnings(self, reports: list[tuple[str, str, list[int]]]) -> None:
        """Log preservation-zone conflicts once per batch."""
        if not reports:
            return
        for relative_path, existing_content, orphan_lines in reports:
            message = format_orphan_edit_message(
                relative_path,
                existing_content,
                orphan_lines,
            )
            if self._strict_preservation:
                raise GenerationError(message)
        if len(reports) == 1:
            relative_path, existing_content, orphan_lines = reports[0]
            message = format_orphan_edit_message(
                relative_path,
                existing_content,
                orphan_lines,
            )
            logger.warning("{}; regeneration may overwrite them", message)
            return
        examples = ", ".join(
            f"{path} ({len(lines)} line(s))"
            for path, _content, lines in reports[:4]
        )
        suffix = "..." if len(reports) > 4 else ""
        logger.warning(
            "Manual edits outside <custom-code> in {} generated file(s) "
            "(regeneration may overwrite). Examples: {}{}",
            len(reports),
            examples,
            suffix,
        )

    def _guard_orphan_edits(self, relative_path: str, existing_content: str) -> None:
        """Legacy hook; prefer batching via :meth:`_emit_orphan_warnings`."""
        orphan_lines = find_orphan_line_numbers(existing_content)
        if not orphan_lines:
            return
        message = format_orphan_edit_message(relative_path, existing_content, orphan_lines)
        if self._strict_preservation:
            raise GenerationError(message)
        if relative_path in self._orphan_warnings_emitted:
            return
        self._orphan_warnings_emitted.add(relative_path)
        logger.warning("{}; regeneration may overwrite them", message)

    def _restore_backup(self, backup_dir: Path, written: list[WriteRecord]) -> None:
        restored: list[str] = []
        for record in written:
            try:
                relative = record.target.relative_to(self._project_dir)
                backup_source = backup_dir / relative
                if backup_source.exists():
                    shutil.copy2(backup_source, record.target)
                elif not record.existed_before and record.target.exists():
                    record.target.unlink()
                restored.append(str(relative))
            except OSError as exc:
                logger.exception(
                    "Rollback step failed for {}: {}",
                    record.target,
                    exc,
                )
                partial = ", ".join(restored) if restored else "none"
                raise GenerationError(
                    f"Rollback failed after partial restore (restored: {partial}); "
                    f"failed on {record.target}: {exc}"
                ) from exc
