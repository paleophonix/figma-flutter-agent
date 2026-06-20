Every plan step must link to a diagnose.laws[].id via lawId.

Every plan step must declare actionKind: CODE_CHANGE, REPORT_ONLY, INFRA_RETRY, or HUMAN_REQUIRED.

Set repairClass from diagnose.laws[].repairShape when present, using the plan repairClass vocabulary (EMITTER_LAW, PARSER, IR_VALIDATION, REPORT_ONLY, POLICY_GATE, CONTRACT_RECOVERY, TOOLCHAIN, and aligned aliases).

CODE_CHANGE steps must name priority, entityIds, repairClass, targetFiles under src/figma_flutter_agent, forbiddenFiles, tests[] with named regression proof, expectedChange, and dependsOn when relevant. Orchestrator routes CODE_CHANGE only to repair.

REPORT_ONLY, INFRA_RETRY, and HUMAN_REQUIRED steps must not route to repair. Use empty targetFiles or omit compiler src paths. REPORT_ONLY closes forensic or diagnostic truth with artifact evidence refs. INFRA_RETRY names a deterministic orchestrator retry (re-capture, re-check, serve probe). HUMAN_REQUIRED escalates to STOP with reason.

On SCREEN board, defer visual fidelity laws to blockedItems when capture.kind is not verified unless run_context documents an explicit capture skip reason for dev-only runs.

Prefer the lowest correct compiler layer named in diagnose. Do not plan fixes in a higher layer to mask a lower-layer law.

Do not plan edits to generated Dart under Flutter app lib, golden baselines, .debug artifacts, or screen-specific production branches.

If a law is blocked, evidence is insufficient, or repair would require a forbidden shortcut, put it in blockedItems[] instead of inventing a fix.

Default scope: P0 and P1 laws must be planned when actionable. P2 is allowed when directly connected to an in-scope P0 or P1 law. P3 is out of scope unless run_context explicitly allows opportunistic P3.

Sort actionable steps by priority P0, then P1, then P2, respecting dependsOn so runtime crashes and write failures precede pixel polish hidden by them.

If plan.steps[] is empty and blockedItems[] does not explain why, set blocked=true on the plan executive JSON.

Repo navigation map deepModules slice helps choose targetFiles and tests; it is not evidence for law linkage.

Do not mutate the cumulative reasoning_chain; write only executive JSON to output_path.

Do not emit a prose BATCH PRE-FIX TRIAGE REPORT or markdown repair queue.
