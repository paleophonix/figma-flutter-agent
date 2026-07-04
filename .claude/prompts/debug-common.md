# Debug Common — canonical `.debug/` doctrine

Every `generate` writes screen artifacts under:

```text
<agent_repo>/.debug/screen/<project>/<feature>/
```

Use `.debug/screen/<project>/<feature>/` at the agent repo root unless the command explicitly uses another `--project-dir`. `<project>` is the Flutter project **folder name** (e.g. `limbo`, `ataev`).

Debug artifacts are for **observation and triage**. They are not a substitute for fixtures, corpus tests, or named layout laws.

**Defect corpus (read-only in `.claude/`):** classify against `families.yaml` and existing
cases; understand `OPEN` / `FIXED` lifecycle when reading. **Do not** create, update, or
index corpus YAML from Claude prompts or skills — **Cursor** (`.cursor/`) owns all writes.

**Corpus lookup (do not glob `corpus/cases/`):**

```text
corpus/families.yaml              → family_id (mechanism, not symptom)
corpus/index/<family_id>.yaml     → case_id, project, feature, status, summary
corpus/cases/<case_id>.yaml       → full occurrence only for the chosen row
```

Rank in index: same `project`+`feature` → `OPEN` → `FIXED` with `repair` → `observed_at` desc.
Indexes under `corpus/index/` are **generated** — read only; never edit by hand from `.claude/`.

---

# Layout model (project-scoped per-screen)

`.debug/screen/` groups screen artifacts by Flutter project under the **agent repo**. All artifacts for a screen live **flat** under `.debug/screen/<project>/<feature>/`. Project metadata lives on the Flutter project root, outside agent `.debug`.

```text
<agent-repo>/
└── .debug/screen/
    └── <project>/              # e.g. limbo, ataev
        ├── shared/
        │   └── full_file_*.json  # batch full-file Figma dumps
        └── <feature>/          # e.g. login_version_1, feedback — flat root
            raw.json
            processed.json
            snapshot.json
            last.log
            dart-errors.json
            renders/
            …

<workspace>/                      # FIGMA_FLUTTER_PROJECT_DIR parent
├── .figma-flutter/workspace-state.yml
└── .sandbox/                   # warm golden capture mini-project

<project_dir>/
├── wizard-state.yml              # active screen slug
├── pubspec_resolve.sha256        # last successful pub get stamp
└── screens.yaml                  # batch manifest (when used)
```

**Naming rule:** project label and feature slug live in the directory path; filenames are **short and stable** (no `<feature>_` prefix). Example: `demo_app/feedback/screen.dart`, not `dart/feedback_screen.dart`.

**Resolve active screen:** read `<project_dir>/wizard-state.yml` (or CLI `--feature`), then open `.debug/screen/<project>/<feature>/` where `<project>` is the Flutter project folder name.

**Gitignored paths:** `sandbox/` and `.debug/` may be invisible to IDE `Grep`/`Glob` — use shell (`Get-ChildItem`, `python`) when artifacts are missing from search.

---

# Hot triage vs deep dive (same folder, read priority)

## Hot triage bundle (~90% of `/diagnose`)

Minimum coherent chain for one generate run on one screen:

```text
Figma truth → parse → pre-emit IR → Dart → visual reference
```

| File | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `raw.json` | Raw Figma REST subtree, truth from API | Fetch/parse bugs, missing nodes, wrong geometry |
| `processed.json` | Parsed clean tree after `parser/tree.py`; classification and IR input | Layout/classification wrong but raw looks fine |
| `pre_emit.json` | IR snapshot immediately before emitter | Emitter/layout mismatch |
| `plan.dart` | Planned Dart bundle, post-planner/pre-write | Planner/template bugs |
| `screen.dart` | Final debug Dart bundle, pre-write gate | Compare vs emitted `lib/` without opening project |
| `figma.png` + `figma.json` | Figma visual gold: PNG + metadata | Pixel/layout fidelity vs Flutter |
| `semantics.json` | Node classification report: BUTTON, INPUT, etc. | Wrong widget types, missed components |
| `run.meta.json` | Run id, timestamp, command, node id (when emitted) | Confirm artifacts belong to the latest run |
| `last.log` | Per-screen pipeline transcript (subprocess stdout/stderr, short analyzer pointers) | Failures, timeouts, stage ordering |
| `dart-errors.json` | Structured `dart analyze` events with full `analyzeOutput` (when analyze fails) | Syntax/analyzer failures, repair stagnation |
| `snapshot.json` | Per-screen incremental sync hashes | What changed since last generate for this screen? |

**Hot read order (fixed):**

```text
last.log → dart-errors.json → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

(`dart-errors.json` when analyze failed; skip if absent.)

## Deep dive / report-only (same `.debug/<project>/<feature>/` folder)

| File | Purpose | When to read |
| ---- | ------- | ------------ |
| `llm_parsed.json` | LLM screen IR right after JSON parse | IR shape/schema issues |
| `llm_validated.json` | IR after `generator/ir/validate.py` guards | Render safety, stack/scroll/token violations |
| `semantic_context.json` | Semantic context package, if emitted | Semantic adjudication/input-context issues |
| `semantic_verdicts.json` | Report-only semantic verdicts, if emitted | What did the IR/LLM think this element is? |
| `element_contracts.json` | Report-only element contracts, if emitted | What control contract was recovered? |
| `contract_emit_diff.json` | Report-only diff: recovered contracts vs current Dart | Known contract says X; current emit does Y |
| `contract_emit_diff.md` | Human-readable contract-vs-emit gap report | Law-based visual/layout triage |
| `provenance.json` | Mutation + classification decision trail | Why did this node become X? |
| `ai_ux.json` | AI UX / a11y / nesting / spacing suggestions | UX polish, touch targets, token drift |
| `animations.json` | Prototype / routing / animation manifest hints | Navigation, transitions |
| `design_coverage.json` | Design coverage gaps, when emitted | Unsupported Figma features |
| `screen.bug.dart` | Dart bundle when analyze/gate failed, if present | Last known bad codegen |
| `emitter_ref.dart` | IR emitter golden bundle, when present | Deterministic emitter regressions |
| `flutter_render.png`, `capture.json`, etc. | Flutter render / diff / manifest | Pixel diff vs `figma.png` |
| `renders/<session>/` | Combat-mode PNG sessions: wizard / visual refine | Interactive refine loops |
| `perf/` | Golden-capture phase timings for this screen | Slow capture / pub get / build |

---

# Project metadata (outside `.debug`)

| Path | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `wizard-state.yml` | Wizard active screen slug | Which `.debug/<project>/<feature>/` to open |
| `pubspec_resolve.sha256` | Stamp of last successful `pub get` | Stale deps / skipped pub get |
| `.figma-flutter/shared/` | Full-file Figma batch dumps | Offline batch / `dump-file` |
| `.figma-flutter/capture-sandbox/` | Shared warm golden capture sandbox | Infrastructure / docker golden, not screen triage |
| `<workspace>/workspace-state.yml` | Active Flutter app under workspace | Multi-app wizard switch |

Agent repo `logs/` is global telemetry only, for example `figma_flutter_agent.log`.

---

# Legacy layouts (deprecated)

Do **not** read or write these for new work; migration v7 flattens on first pipeline touch:

```text
# v3 screen-centric (primary/secondary shards)
<feature>/primary/*
<feature>/secondary/*
.debug/logs/last.log
.debug/sync/snapshot.json
.debug/wizard-state.yml
.debug/pubspec_resolve.sha256
.debug/capture/sandbox/
.debug/.artifact-layout-v3

# v2 domain folders
raw/<feature>_layout.json
processed/<feature>_layout.json
ir/<feature>_*.json
dart/<feature>_plan.dart
dart/<feature>_screen.dart
…
```

Canonical path helpers: `src/figma_flutter_agent/debug/paths.py` (layout v9, `ARTIFACT_LAYOUT_VERSION = 9`).

---

# Core doctrine

Debugging has two phases:

```text
Phase 1 — Diagnosis / Triage
  Goal: identify the violated contract/law and responsible pipeline layer.
  Output: evidence-based triage report.
  No code changes.

Phase 2 — Repair
  Goal: implement the approved law-level fix in the approved layer only.
  Output: targeted fix + regression proof.
```

An agent must not move from Diagnosis to Repair without explicit approval of:

```text
target bug class
target law
files allowed to touch
tests to add/change
expected behavior change
```

---

# Final invariant

Do not fix the screen.

Fix the law.

A screen is only evidence.
A visual bug is only a symptom.
A durable fix must map to:

```text
ElementContract
ContractEmitRecipe
LayoutLaw
PolicyGate
EmitterLaw
CorpusTest
```

---

# Not always present

```text
<feature>/last.log
<feature>/dart-errors.json
<feature>/flutter_render.png
<feature>/renders/
<feature>/perf/
<feature>/emitter_ref.dart
<feature>/screen.bug.dart
<feature>/semantic_context.json
<feature>/semantic_verdicts.json
<feature>/element_contracts.json
<feature>/contract_emit_diff.*
<feature>/run.meta.json
fidelity.json
```

Deprecated agent-repo paths are not valid debugging sources:

```text
logs/figma-debug
logs/dart
logs/reports
logs/semantics
logs/dart-errors/          # legacy per-run JSONL folder (migrated away)
terminal/
```

Do not read or write them for screen debugging. Use `<agent_repo>/.debug/<project>/<feature>/dart-errors.json` instead of legacy `logs/dart-errors/`.

---

# Universal forbidden shortcuts

Compiler-wide anti-patching and codegen bans: `project-bible-lite.md` (Anti-Patching, Forbidden).

Additional bans during diagnosis or repair:

```text
debugging from deprecated agent logs instead of .debug
hand-editing generated lib/ in customer projects to pass
changing repair bot while debugging emitter/layout
changing preview/oracle flow while debugging emitter/layout
vector degradation side quests while debugging inputs/buttons/chips
mixing unrelated contract kinds in one fix
LLM-generated Dart
direct semanticVerdict -> emit without policy gate
```

---

# Batch repair rule (default)

A debugging session should **diagnose all symptoms** and **repair all in-scope queue items** (P0 → P1 → P2) in one pass unless the user narrowed scope.

Each queue item still obeys:

```text
one named law
one responsible layer (primary)
regression test or fixture proof
no anti-patching shortcuts
```

Multiple items in one session/PR is **expected** when they come from the same `BATCH PRE-FIX TRIAGE REPORT`.

**Single-layer PR guidance** (legacy): prefer splitting **unrelated** epics across PRs for review — not one micro-PR per comma on the same screen failure.

Do not combine in one diff without diagnosis:

```text
unrelated drive-by refactors
baseline updates to hide failure
screen-specific node-id branches
```

---

# Acceptable fix rule

Same bar as `project-bible-lite.md` (Acceptable Fix). During repair, also name the violated law, responsible layer, and fixture proof before touching code.
