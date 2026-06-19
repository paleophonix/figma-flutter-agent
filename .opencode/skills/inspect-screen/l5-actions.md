Confirm agent_board=screen, case_mode=SCREEN, capture.kind=verified when required by run_context, and recognise.symptoms[] is present. If symptoms are missing, set blocked=true.

For each symptom, identify minimal artifact anchors: semantics.json, screen.dart, plan.dart, pre_emit.json, processed.json, contract_emit_diff.*, figma.json, dart-errors.json, or capture.json metadata as applicable. Do not read figma.png or vision bundle images.

Follow the artifact chain upstream only as needed. Do not full-dump raw.json unless fetch or parse truth is suspected for that symptom.

Map artifact anchors to likely repo surfaces under src/figma_flutter_agent using targeted grep and read. Stay within surfaces implied by the chain.

Consolidate overlapping anchors into entities[]. Each entity represents one compiler concern, not one screen region and not the whole screen.

Emit entities[] with id, relatesToSymptoms, kind, role, artifactRefs, repoPaths when known, summary as WHERE-only prose, and confidence high, medium, or low.

Allowed kind values: debug_artifact, compiler_module, control_surface. Allowed role values include parser, ir, validator, planner, emitter, style, shell, semantic, contract, analyzer.

If a symptom cannot be anchored to artifactRefs and repoPaths, set blocked=true and list missing_evidence[]. An entity may be artifact-only only when blocked documents why repo surface is unavailable.

Do not output laws, root causes, fixes, repair plans, visual descriptions, or causal language such as because, should fix, violates, or change X to Y in summary fields.

Write only executive JSON to output_path.
