# Debug artifacts

Screen debug output lives in the **agent repo**, not inside the Flutter project.

## Layout (v9+)

```text
<agent_repo>/
└── .debug/screen/<project>/<feature>/   # e.g. limbo/login_version_1
    raw.json              # Figma REST subtree
    processed.json        # parsed clean tree
    pre_emit.json         # IR immediately before emitter
    plan.dart             # planned Dart bundle
    screen.dart           # final debug Dart bundle
    figma.png + figma.json
    semantics.json
    snapshot.json         # incremental sync hashes
    last.log
    dart-errors.json      # when analyze failed
    renders/<session>/    # combat-mode PNG sessions
    perf/
    llm_parsed.json
    llm_validated.json
    provenance.json
    contract_emit_diff.json
    ai_ux.json
    animations.json
    …

<agent_repo>/.debug/screen/<project>/shared/
    full_file_<FILE_KEY>.json

<flutter_project>/
    screens.yaml
    wizard-state.yml
    pubspec_resolve.sha256
    lib/features/
```

Warm golden capture sandbox: `<workspace>/.sandbox/` (not per-screen `.debug`).

Legacy `demo_app/.debug/raw/*` paths migrate automatically on first pipeline touch.

## Hot triage read order

```text
last.log → dart-errors.json → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

Skip `dart-errors.json` when analyze passed.

## Resolve active screen

1. Read `<project_dir>/wizard-state.yml` (or CLI `--feature`)
2. Open `<agent_repo>/.debug/screen/<project>/<feature>/` where `<project>` is the Flutter folder name (e.g. `limbo`)

Canonical path helpers: `src/figma_flutter_agent/debug/paths.py`.

Repair doctrine for coding agents: [AGENTS.md](../../../AGENTS.md), `.cursor/rules/debug-context.mdc`.
