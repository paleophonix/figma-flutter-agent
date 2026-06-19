"""Batch multi-screen testing for figma-flutter-agent."""

from figma_flutter_agent.batch.file_dump import FileDumpResult, dump_full_figma_file
from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry, load_batch_manifest

__all__ = [
    "BatchManifest",
    "FileDumpResult",
    "ScreenEntry",
    "dump_full_figma_file",
    "load_batch_manifest",
]
