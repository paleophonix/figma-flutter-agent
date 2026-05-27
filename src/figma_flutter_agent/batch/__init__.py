"""Batch multi-screen testing for figma-flutter-agent."""

from figma_flutter_agent.batch.file_dump import FileDumpResult, dump_full_figma_file
from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry, load_batch_manifest
from figma_flutter_agent.batch.run import BatchRunReport, run_batch_generate

__all__ = [
    "BatchManifest",
    "BatchRunReport",
    "FileDumpResult",
    "ScreenEntry",
    "dump_full_figma_file",
    "load_batch_manifest",
    "run_batch_generate",
]
