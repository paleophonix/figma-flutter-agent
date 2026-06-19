Worktree: {worktree}
Project: {project}
Feature: {feature}
Case mode: {case_mode}
Agent board: forensic
Step: inspect (2/7)

Debug root: {debug_root}
Run manifest: {run_manifest_path}
Schema: {schema_path}
Output path: {output_path}
Detail log path: {detail_log_path}

Run context:
{run_context_json}

Cumulative reasoning chain:
{reasoning_chain_json}

Inspect preflight (artifact index, stage markers, symptom anchors; not a fat dump):
{inspect_preflight_json}

Repo navigation map (forensic surfaces only; navigation not evidence):
{repo_map_compact_json}

Use artifactRefs relative to the worktree. Use repoPaths relative to the worktree sandbox root.

Do not inspect figma.png, capture images, or vision bundle artifacts on the forensic board.
