Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: screen
Step: inspect (2/7)

Debug root: {debug_root}
Manifest: {manifest_path}
Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Run context:
{run_context_json}

Cumulative reasoning chain:
{reasoning_chain_json}

Inspect preflight (artifact index, symptom anchors, compact semantic index; not a fat dump):
{inspect_preflight_json}

Repo navigation map (curated; navigation only, not evidence):
{repo_map_compact_json}

Symptom-to-surface hints (matched from recognise.symptoms[].id when available):
{symptom_surface_hints_json}

Use the repo map only to choose reads. Do not treat the map as evidence or root cause.

Read case materials from disk only when needed to anchor a symptom to a compiler surface. Do not inspect vision bundle images on this step.
