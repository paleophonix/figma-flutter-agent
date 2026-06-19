You can inspect orchestrator-prepared watermarked vision artifacts under the vision bundle directory:

01_FIGMA_REFERENCE watermark bar and image
02_FLUTTER_CAPTURE watermark bar and image
03_COMPARE_REF_CAPTURE side-by-side strip
04_DIFF_HEATMAP watermark bar and image

Optional: 05_COMPARE_REF_CAPTURE_DIFF three-panel grid when provided.

You can use compact JSON injected in run_context or vision_bundle: capture_kind, captured_run_id, served_build_run_id, changed_ratio, diff threshold, semantic_hints, and diff.largestRegions when present.

You may read figma.json metadata from disk only for screen title or frame size hints, not for layout law diagnosis.

You must output executive JSON matching the recognise schema with symptoms[] entries: id, severity, userVisible, regions, visualEvidence, confidence, and optional semanticHints.
