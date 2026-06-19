Use run_manifest, run_context, and gate outputs as primary truth. Do not use Chrome or preview UI as current product state.

Do not emit user-visible layout symptoms such as misaligned buttons when case_mode is FORENSIC or capture is not verified.

Symptoms must describe pipeline failure modes: rollback, stale capture, no serve, write failure, analyze failure, stale runIds, or missing artifacts.

Do not name repo files, law ids, or root-cause fixes. Do not assign compiler layers beyond high-level stage names such as write, capture, or serve.

If FRESH_OK and verified capture appear later, the orchestrator will switch boards; do not mix forensic and screen symptoms in one pass.

Do not mutate the cumulative reasoning_chain. Write only executive JSON to output_path.
