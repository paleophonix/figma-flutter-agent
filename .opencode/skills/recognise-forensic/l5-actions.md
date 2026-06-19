Confirm case_mode=FORENSIC or blocked SCREEN path from run_context.

Read run_manifest verdict, writeback, runId alignment, capture.kind, and served_build_run_id probe results.

Read last.log and dart-errors.json only as needed to name the failing stage in user-visible but non-layout terms.

Emit symptoms[] describing untrusted build output, for example rollback after failed write, stale capture, or missing serve probe.

Use severity P0 for hard blockers preventing trustworthy screen diagnosis. Use regions such as pipeline, write, capture, serve rather than header or primary_cta.

Do not emit visual comparison symptoms, figmaId references, or law ids.

If evidence is insufficient, set blocked=true and list missing_evidence.

Write only executive JSON to output_path.
