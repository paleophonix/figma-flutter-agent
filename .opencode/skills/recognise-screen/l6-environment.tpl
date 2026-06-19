Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: screen
Step: recognise (1/7)

Debug root: {debug_root}
Vision bundle dir: {vision_bundle_dir}
Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Vision bundle (watermarked; read in pass order A→B→C→D):
{vision_bundle_json}

Diff statistics (orchestrator-computed; do not re-estimate from pixels):
{diff_stats_json}

Semantic hints (compact; optional cross-check only):
{semantic_hints_json}

Run context:
{run_context_json}

Full semantics.json and raw capture artifacts are on disk under the debug root. Read only if hints are insufficient for inventory cross-check.

Do not paste image bytes or full JSON dumps into executive JSON.
