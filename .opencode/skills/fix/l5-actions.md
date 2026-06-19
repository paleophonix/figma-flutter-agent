Confirm check_summary.failure_class is PATCH_CODE_EMIT. If not, set blocked=true and stop without edits.

Confirm attempt is less than or equal to maxAttempts and allowedEditFiles is non-empty. If FORENSIC, confirm candidate_available and fix_purpose allow candidate materialization fix.

Read analyze_errors and locate each error in allowedEditFiles only.

Apply the smallest candidate Dart patch that addresses the concrete analyzer or parser errors. Do not change compiler source or expand scope beyond allowedEditFiles.

Write changed files under .repair/candidate/planned_files/. Do not patch chat-only unified diffs as substitute for file edits.

Emit fix.json with step fix, phase emit_materialization, attempt, maxAttempts, failure_class, same_root_hash, allowedEditFiles, filesTouched, errorsBefore, expectedErrorsAfter, diagnoseLawIdsFrozen, planStepOrders, blocked, exhausted, routeAfter, and notes.

Do not run check, capture, dart analyze gates, or review. Do not close laws or claim task completion.

Write only executive JSON to output_path.
