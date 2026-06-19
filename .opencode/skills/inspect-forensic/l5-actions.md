Confirm agent_board=forensic and case_mode=FORENSIC.

Read recognise.symptoms[] for pipeline-trust symptoms only. Do not add visual fidelity symptoms.

Anchor each symptom in run_manifest.json, last.log stage markers, dart-errors.json, capture passport fields, rollback or writeback state, served probe results, or candidate artifact availability.

Map anchors to pipeline repo surfaces using targeted read and grep: stages/write.py, pipeline/run modules, debug/capture.py, dev/opencode/run_gate.py, failure_class or run_gate helpers, and analyzer repair loop modules only when directly relevant.

Consolidate into entities[] by pipeline concern, not by screen region.

Emit entities[] with id, relatesToSymptoms, kind, role, artifactRefs, repoPaths, WHERE-only summary, and confidence.

Allowed kind values: debug_artifact, pipeline_module, toolchain_surface. Allowed role values include run_gate, write, analyze, capture, serve, rollback, snapshot, toolchain, orchestrator.

If a symptom cannot be anchored, set blocked=true and list missing_evidence[].

Do not output laws, screen root cause, visual layout entities, fixes, or repair plans.

Write only executive JSON to output_path.
