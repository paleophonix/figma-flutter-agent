"""Oversized layout chunking — superseded by test_ir_chunking.py.

The original fig-leaf test only checked that split_oversized_layout_dart returned
multiple paths and that sizes fit.  It did NOT compile the result or verify class
connectivity.  Comprehensive tests are in test_ir_chunking.py (IR-level chunking).
"""

from __future__ import annotations

# Re-export the real tests so this file stays in the collection without duplication.
from tests.test_ir_chunking import (  # noqa: F401
    test_render_layout_file_all_chunks_under_budget,
    test_render_layout_file_chunk_imports_in_layout,
    test_render_layout_file_class_names_not_broken,
    test_render_layout_file_small_tree_unchanged,
)
