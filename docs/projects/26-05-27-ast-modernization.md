# AST modernization — compiler pipeline + dual golden runtime

**Status:** S5 plan (approved concept: variant 3 from S4)  
**Target:** ~2 engineering days (parallel workstreams)  
**Owner:** figma-flutter-agent team  
**Last updated:** 2026-05-27

---

## S1 — Goal & Definition of Done

### Problem

- LLM screen bodies are “fixed” with **regex postprocess** (`dart_postprocess.py`, `strip_llm_*` in `subtree_widgets.py`) — fragile, not universal.
- **Visual refine** compares full-frame PNGs and asks LLM to rewrite large regions — expensive and unstable.
- **Golden capture** runs on **host** `flutter test` — pixel drift across OS/GPU/fonts.
- **Semantic typing** leans on layer names / marketing copy — fails AC-2 (dirty Cyrillic names).

### Goal (SMART)

| | |
|---|---|
| **Specific** | Replace regex Dart edits with **AST sidecar**; add **geometry classifier**; **IoU surgical refine** with `figma-id`; **Docker CanvasKit** golden with `golden_capture: auto\|docker\|host`. |
| **Measurable** | AC-1…AC-4 green in Docker signoff; `signoff.ps1` green; one live Figma smoke (`sign_in` or configured smoke URL). |
| **Achievable** | MVP AST rule set + 4 layout fixtures + docker image v1. |
| **Relevant** | Universal codegen; no hand-edits in `demo_app`. |
| **Time-bound** | 2-day plan below; stretch items marked optional. |

### Definition of Done

**Release (CI / merge to `main`):**

- [ ] `.\scripts\signoff.ps1` passes with **pytest + golden** executed **inside Docker** (host: ruff, mypy, demo-signoff static gates only).
- [ ] `tests/fixtures/screens.yaml` — all entries pass in Docker (`UPDATE_GOLDEN=0`).
- [ ] AC-2: `music_v2_ru_dirty` classifies social row **without** English label strings.
- [ ] AC-3: IoU refine changes **only** widgets under threshold on a failing fixture (unit test with synthetic diff).
- [ ] AC-4: `ast_compiler` subprocess; **no regex** in `reconcile_planned_dart_files` prod path; AST failure → `llm_repair` ≤3.
- [ ] `poetry run figma-flutter doctor` reports sidecar + Docker status.
- [ ] One manual live generate smoke documented in test log (not necessarily in CI).

**Dev (local, host allowed):**

- [ ] `poetry run figma-flutter generate` on `sign_in` completes; `flutter analyze` clean in `demo_app`.
- [ ] `golden_capture: auto` falls back to host with **one** warning line when Docker missing.

### Out of scope (this project)

- Melos monorepo (optional stretch).
- Removing all `subtree_widgets` vector reconcile (keep placement/asset fixes; drop scale/LayoutBuilder strips).
- `use_deterministic_screen: true` as default.
- Shipping full Figma files in git (layouts are **synthetic clean-tree JSON** only).

---

## S4 recap — approved concept

**Variant 3:** compiler bottom-up + dual runtime.

1. **Layer 0 (parallel):** fixtures manifest, AST sidecar binary, Docker render-capture skeleton.  
2. **Layer 1:** wire AST into `planned_dart`; geometric classifier v1; burn regex strips from reconcile.  
3. **Layer 2:** `figma-id`, IoU refine, golden routing, signoff split, doctor/bootstrap.

**Runtime product model:**

| Mode | Default | CI | Behavior |
|------|---------|-----|----------|
| `auto` | yes | — | Docker if available + image OK → docker; else host + warn |
| `docker` | — | yes | Fail if Docker unavailable |
| `host` | — | — | `--no-docker`; best-effort pixels |

Config keys (to implement):

```yaml
runtime:
  golden_capture: auto   # auto | docker | host
```

```env
FIGMA_GOLDEN_RUNTIME=auto
```

CLI: `--golden-runtime`, `--no-docker` (forces host).

---

## Architecture

### Pipeline (target)

```
Figma REST → parse (geometry + layout) → LLM generate
    → AstSidecarClient (tools/bin/ast_compiler[.exe])
    → dart analyze → llm_repair (≤3)
    → [optional] visual refine: golden (auto/docker/host) → pixeldiff → IoU map → surgical LLM → AST patch
    → write demo_app
```

### New / major modules

| Path | Role |
|------|------|
| `tools/dart_ast_sidecar/` | Dart package: `package:analyzer`, JSON IPC, `ChangeBuilder` edits |
| `tools/bin/ast_compiler.exe` (+ linux x64 for CI) | Prebuilt `dart compile exe` artifacts |
| `tools/build_sidecars.sh` | Build linux-x64 + windows-x64 |
| `src/figma_flutter_agent/tools/ast_sidecar.py` | Python client: spawn, timeout, fail → repair hint |
| `src/figma_flutter_agent/parser/geometry.py` | Bbox, sibling similarity, reactions, layoutMode |
| `src/figma_flutter_agent/validation/golden_runtime.py` | `auto` / `docker` / `host` router |
| `docker/render-capture/` | Dockerfile, compose, capture script, offline fonts |
| `tests/fixtures/screens.yaml` | Canonical fixture manifest |
| `tests/fixtures/layouts/*.json` | Synthetic clean-tree layouts |
| `tests/fixtures/flutter_skeleton/lib/harness/element_coordinate_mapper.dart` | Test-only IoU helper |

### Modules to shrink / replace

| Path | Action |
|------|--------|
| `generator/dart_postprocess.py` | Deprecate prod entry; migrate rules to AST; delete when parity tests pass |
| `generator/subtree_widgets.py` | Remove `strip_llm_viewport_scale_hack`, `strip_llm_responsive_layout_builder` from reconcile chain |
| `validation/golden_capture.py` | Delegate capture to `golden_runtime` |
| `stages/visual_refine.py` | IoU-targeted surgical refine |
| `scripts/signoff.ps1` | Split host static vs docker pytest |

---

## Workstreams & schedule (~2 days)

### Stream A — AST sidecar (owner: compiler)

| Block | Hours | Deliverable |
|-------|-------|-------------|
| A1 Dart package scaffold | 2h | `tools/dart_ast_sidecar/pubspec.yaml`, `bin/ast_compiler.dart`, JSON protocol |
| A2 MVP rules | 4h | Rules ported from highest-value regex: unscale `* scaleX/Y`, unwrap scale `LayoutBuilder`, fix `Colors.transparent` social fills (generic signals), import cleanup |
| A3 Build + prebuilt | 2h | `build_sidecars.sh`, `tools/bin/ast_compiler.exe` committed or LFS |
| A4 Python client + wire | 3h | `ast_sidecar.py`, `planned_dart.reconcile` calls AST first |
| A5 Tests | 2h | `tests/test_ast_sidecar.py` — same cases as existing `test_dart_postprocess_*` critical subset |

**Merge point M1 (end day 1):** AST processes planned dart in pytest on host (no Docker yet).

### Stream B — Fixtures & geometry (owner: parser)

| Block | Hours | Deliverable |
|-------|-------|-------------|
| B1 `screens.yaml` | 1h | Manifest schema + 4 screens |
| B2 Layout JSON files | 3h | Synthetic trees (see below) |
| B3 `geometry.py` v1 | 4h | `classify_social_auth_row`, `classify_primary_cta` by bbox + child count + INSTANCE metadata |
| B4 Integrate `tree.py` | 2h | `resolve_semantic_node_type` prefers geometry when confidence ≥ threshold |
| B5 AC-2 test | 1h | `test_geometry_music_v2_ru_dirty.py` |

**Merge point M2 (day 1 PM):** layout fixtures load in pytest; classifier unit tests green.

### Stream C — Docker golden (owner: infra)

| Block | Hours | Deliverable |
|-------|-------|-------------|
| C1 Spike Flutter web flags | 1h | Document single `flutter build web` command for pinned SDK (read from `demo_app/pubspec.yaml` `environment.sdk` or new `.flutter-version` at agent root) |
| C2 `docker/render-capture/Dockerfile` | 3h | Flutter SDK, Chrome, Xvfb, CanvasKit, bundled fonts |
| C3 Capture entrypoint | 3h | Mount `tests/fixtures/flutter_skeleton`, run golden test, emit PNG to volume |
| C4 `golden_runtime.py` | 2h | `auto`/`docker`/`host`; compose wrapper |
| C5 Baseline | 2h | `UPDATE_GOLDEN=1` **inside Docker only** for all `screens.yaml` entries |

**Merge point M3 (day 2 AM):** one fixture golden PNG stable in Docker.

### Stream D — IoU refine + anchoring (owner: vision)

| Block | Hours | Deliverable |
|-------|-------|-------------|
| D1 `figma-id` emission | 2h | Writer adds `// figma-id: <nodeId>` or `key: ValueKey('figma-<id>')` on positioned widgets |
| D2 `ElementCoordinateMapper` | 3h | Harness-only: parse keys → rects from golden test |
| D3 IoU in `pixeldiff` / new `iou.py` | 2h | Per-widget IoU vs Figma node bbox (from clean tree + scale) |
| D4 Surgical refine prompt | 3h | LLM gets **only** failing widget snippets + structured schema |
| D5 AST extract/replace | 2h | Sidecar `extract_widget` / `replace_widget` for patch apply |

**Merge point M4 (end day 2):** visual refine loop uses IoU on fixture; full signoff green in Docker.

### Stream E — DX & signoff (owner: CLI)

| Block | Hours | Deliverable |
|-------|-------|-------------|
| E1 `figma-flutter doctor` | 2h | Poetry, Flutter, sidecar binary, Docker, image tag |
| E2 `scripts/bootstrap.ps1` | 1h | Pull/build docker, verify sidecar |
| E3 `signoff.ps1` / `signoff.sh` | 2h | Host: ruff, mypy, pyright (if added), `dart analyze` agent fixtures; Docker: pytest |
| E4 Config + CLI flags | 1h | `RuntimeConfig` in `config.py`, `.ai-figma-flutter.yml.example` |
| E5 Docs | 1h | README section, AGENTS.md pointer |

---

## Fixture manifest

### `tests/fixtures/screens.yaml` (schema)

```yaml
version: 1
screens:
  - id: sign_up_and_sign_in
    layout: layouts/sign_up_and_sign_in_layout.json
    feature: auth
    golden_id: sign_up_and_sign_in
    description: Dual auth stack; social row + email fields

  - id: reminders
    layout: layouts/reminders_layout.json
    feature: reminders
    golden_id: reminders

  - id: music_v2
    layout: layouts/music_v2_layout.json
    feature: music
    golden_id: music_v2

  - id: music_v2_ru_dirty
    layout: layouts/music_v2_ru_dirty_layout.json
    feature: music
    golden_id: music_v2_ru_dirty
    ac2: true   # geometry must not use layer names
```

### Layout JSON files (create)

| File | Purpose |
|------|---------|
| `tests/fixtures/layouts/sign_up_and_sign_in_layout.json` | Sign-in/up patterns: social row, stacked fields, CTA |
| `tests/fixtures/layouts/reminders_layout.json` | List + cards + FAB |
| `tests/fixtures/layouts/music_v2_layout.json` | Player chrome, tabs, media controls |
| `tests/fixtures/layouts/music_v2_ru_dirty_layout.json` | Same geometry as music_v2; **Cyrillic** `text` fields; garbage `name` on layers (`"слой 123"`, `"Rectangle 999"`) |

Each file: serialized **clean design tree** (same shape as parser output), not raw Figma API dump. Build from existing `tests/fixtures/figma_*.json` patterns where possible.

### Acceptance criteria (tests)

| ID | Test | Pass condition |
|----|------|----------------|
| AC-1 | `test_screens_manifest_golden_docker` | All `screens.yaml` entries: pixel diff ≤ `validation.pixel_diff_threshold` (0.05) in **docker** runtime |
| AC-2 | `test_geometry_music_v2_ru_dirty` | Social row `semantic_type` correct with **names stripped** from classifier input |
| AC-3 | `test_iou_surgical_refine_scoped` | Mock diff on one widget → LLM payload contains only that widget’s Dart; file line count delta < 15% of screen |
| AC-4 | `test_no_regex_postprocess_in_reconcile` | `reconcile_planned_dart_files` does not import `postprocess_generated_dart`; AST called; on AST error → repair stage invoked (max 3) |

---

## AST sidecar — IPC contract (v1)

### Request (stdin JSON)

```json
{
  "version": 1,
  "command": "apply_rules",
  "sourcePath": "optional/path.dart",
  "source": "<full dart source>",
  "rules": ["unscale_design_expressions", "unwrap_scale_layout_builder", "social_button_fill"],
  "options": {"includeTextScaler": true}
}
```

### Response (stdout JSON)

```json
{
  "ok": true,
  "source": "<patched>",
  "edits": [{"rule": "unscale_design_expressions", "offset": 120, "length": 8}],
  "errors": []
}
```

On `ok: false`, Python logs `errors` and triggers `llm_repair` with `analyze_stage: ast_sidecar` (max **3** attempts — align `llm_repair_max_attempts` default to 3 in example YAML only if product agrees).

### Commands (v1 scope)

| Command | Purpose |
|---------|---------|
| `apply_rules` | Batch MVP transforms |
| `extract_widget` | Return method/class source by name or `figma-id` key |
| `replace_widget` | Splice patched widget back |

**Forbidden:** regex fallback in Python for the same transforms.

### Binary resolution

```text
tools/bin/ast_compiler.exe     # Windows
tools/bin/ast_compiler-linux   # Linux CI / Docker
```

Env override: `FIGMA_AST_COMPILER_PATH`.

---

## Docker render-capture

### Layout

```text
docker/
  render-capture/
    Dockerfile
    docker-compose.yml
    scripts/capture.sh
    fonts/          # optional bundled TTF
```

### Compose service (concept)

- Service `golden-capture`
- Volumes: repo `tests/fixtures`, output `tests/fixtures/golden/png/docker/`
- Env: `FLUTTER_VERSION` build-arg, `GOLDEN_SCREEN_ID`, `UPDATE_GOLDEN`

### 0.3 spike (recorded)

| Item | Value |
|------|--------|
| Base image | `ghcr.io/cirruslabs/flutter:3.29.0` (matches `.flutter-version`) |
| Capture command | `flutter test test/golden/{feature}_screen_test.dart --update-goldens` inside container (`docker/render-capture/scripts/capture.sh`) |
| Web / CanvasKit | Golden harness uses **VM/widget tests**, not `flutter build web`; no separate CanvasKit web build in v1 |
| Host alternative | Set `FIGMA_FLUTTER_SDK` → `poetry run python scripts/generate_fixture_goldens.py --golden-runtime host` |
| Baseline writer | `scripts/generate_fixture_goldens.py` → `tests/fixtures/golden/png/docker/{golden_id}.png` |

### Signoff integration

`signoff.ps1`:

```powershell
# Host
poetry run ruff check .
poetry run mypy src tests
poetry run figma-flutter demo-signoff --strict --signoff-gates

# Docker (required for merge)
docker compose -f docker/render-capture/docker-compose.yml run --rm golden-capture pytest -q -m "not live_figma"
```

---

## Config changes

### `AgentYamlConfig` — add

```python
class RuntimeConfig(BaseModel):
    golden_capture: Literal["auto", "docker", "host"] = "auto"
```

### `.ai-figma-flutter.yml.example` — add block

```yaml
runtime:
  golden_capture: auto
```

### `GenerationConfig` — document only

- Keep `use_deterministic_screen: false` for visual quality (user preference).
- `llm_visual_refine_threshold: 0.1` (existing) vs manifest `pixel_diff_threshold: 0.05` — manifest is **golden gate**; refine loop may use generation threshold.

---

## Regex → AST migration map

| Current (`dart_postprocess.py` / reconcile) | AST rule ID | Priority |
|-----------------------------------------------|-------------|----------|
| `unscale_design_expressions` | `unscale_design_expressions` | P0 |
| `strip_llm_responsive_layout_builder` | `unwrap_scale_layout_builder` | P0 |
| `fix_llm_dart_api_mistakes` (subset) | `fix_api_mistakes` | P1 |
| Social Material/Container fixes | Prefer **geometry** in planner; AST `social_button_fill` as safety net | P1 |
| Text scaler injection | `ensure_text_scaler` | P2 |
| Remaining 1.4k lines | Port only if covered by failing test; else delete | P2+ |

After M1+M4: delete `postprocess_generated_dart` call from `reconcile_planned_dart_files`.

---

## Risk register

| Risk | P | Mitigation |
|------|---|------------|
| Flutter web renderer flag churn | P0 | C1 spike day 1; pin SDK in Dockerfile |
| `ast_compiler` cross-compile | P0 | Prebuilt in repo; CI builds linux artifact |
| Large `source` over IPC | P1 | Temp file + `sourcePath`; 10MB cap |
| Host vs Docker golden mismatch | P1 | CI only docker; host goldens gitignored or separate suffix |
| IoU false positives | P2 | Min IoU 0.5; max 3 widgets per refine iteration |
| 2-day slip | P1 | Ship M1+M2+M3; D IoU as stretch with full-frame refine fallback behind flag |

---

## КОНТРОЛЬНЫЙ СПИСОК (implementation)

Отмечать `[x]` в этом файле по мере S6. Порядок — рекомендуемый; параллельные потоки A/B/C допустимы до merge points.

### Phase 0 — Prep

- [x] **0.1** Create branch `feat/ast-modernization`
- [x] **0.2** Add `.flutter-version` at agent root (match `demo_app` SDK) OR document SDK read from pubspec
- [x] **0.3** C1 spike: VM golden harness flags recorded (§ Docker — no `build web` in v1)

### Phase 1 — Fixtures & manifest (Stream B)

- [x] **1.1** Add `tests/fixtures/screens.yaml`
- [x] **1.2** Add `tests/fixtures/layouts/sign_up_and_sign_in_layout.json`
- [x] **1.3** Add `tests/fixtures/layouts/reminders_layout.json`
- [x] **1.4** Add `tests/fixtures/layouts/music_v2_layout.json`
- [x] **1.5** Add `tests/fixtures/layouts/music_v2_ru_dirty_layout.json`
- [x] **1.6** `tests/test_screens_manifest.py` — loads YAML, validates paths
- [x] **M2** pytest: manifest tests green

### Phase 2 — AST sidecar (Stream A)

- [x] **2.1** Scaffold `tools/dart_ast_sidecar/`
- [x] **2.2** Implement IPC v1 (`apply_rules`)
- [x] **2.3** Rules: `unscale_design_expressions`, `unwrap_scale_layout_builder`
- [x] **2.4** `tools/build_sidecars.sh` + Windows exe in `tools/bin/` (script ready; binaries built on maintainer machine)
- [x] **2.5** `src/figma_flutter_agent/tools/ast_sidecar.py`
- [x] **2.6** Wire `reconcile_planned_dart_files` → AST (feature flag `runtime.use_ast_sidecar: true` for gradual rollout, default true at end)
- [x] **2.7** Port critical tests from `test_dart_postprocess*` to `test_ast_sidecar.py`
- [x] **M1** pytest AST tests green on host

### Phase 3 — Geometry classifier (Stream B)

- [x] **3.1** `parser/geometry.py` with pure bbox/layout functions
- [x] **3.2** Integrate via `enrich_clean_tree_from_geometry` in `build_clean_tree`
- [x] **3.3** AC-2 test `test_geometry_music_v2_ru_dirty.py` (`tests/test_geometry_ac2.py`)
- [x] **3.4** Remove reconcile calls: `strip_llm_viewport_scale_hack`, `strip_llm_responsive_layout_builder` from `subtree_widgets`
- [x] **3.5** Update `llm/prompts.py` — keep `_STACK_FOREGROUND_LAYOUT_RULE` (still valid policy)

### Phase 4 — Docker golden (Stream C)

- [x] **4.1** `docker/render-capture/Dockerfile` + compose
- [x] **4.2** `validation/golden_runtime.py` (`auto`/`docker`/`host`)
- [x] **4.3** Refactor `golden_capture.py` to use runtime router
- [x] **4.4** CLI `--golden-runtime`, `--no-docker` + `figma-flutter doctor`
- [x] **4.5** `UPDATE_GOLDEN=1` script `scripts/update-golden-docker.ps1` + `scripts/bootstrap.ps1`
- [x] **4.6** Regenerate baselines: `scripts/generate_fixture_goldens.py --golden-runtime host` (4 PNGs under `tests/fixtures/golden/png/docker/`)
- [x] **AC-1 infra** `tests/test_fixture_golden_ac1.py` (stability + baseline compare)
- [x] **M3** AC-1 golden baselines for all four manifest screens (host capture; commit PNGs)

### Phase 5 — IoU surgical refine (Stream D)

- [x] **5.1** Emit `figma-id` / `ValueKey` in writer (`generator/writer` or screen template)
- [x] **5.2** `flutter_skeleton` harness: `element_coordinate_mapper.dart`
- [x] **5.3** `validation/iou.py` + integrate `visual_refine.py`
- [x] **5.4** Surgical LLM prompt + structured output schema (strict JSON)
- [x] **5.5** AST `extract_widget` / `replace_widget`
- [x] **5.6** AC-3 test
- [x] **M4 (unit)** `tests/test_m4_surgical_apply.py` — extract/apply surgical patches without LLM
- [ ] **M4 (docker)** End-to-end visual refine + capture on one fixture in Docker

### Phase 6 — Burn regex path (Stream A+E)

- [x] **6.1** Remove `postprocess_generated_dart` from `reconcile_planned_dart_files`
- [x] **6.2** AC-4 test (`tests/test_ac4_reconcile_ast.py`)
- [x] **6.3** Renderer uses `process_generated_dart_source` (AST + codegen); `postprocess_generated_dart` legacy shim only
- [x] **6.4** `llm_repair_max_attempts: 3` in `.ai-figma-flutter.yml.example`

### Phase 7 — DX & signoff (Stream E)

- [x] **7.1** `figma-flutter doctor`
- [x] **7.2** `scripts/bootstrap.ps1`
- [x] **7.3** Update `signoff.ps1` / `signoff.sh` (docker pytest via `FIGMA_SIGNOFF_DOCKER=1`)
- [x] **7.4** Update `.ai-figma-flutter.yml.example`, `AGENTS.md`, README (dual runtime)
- [ ] **7.5** Optional: pre-commit hook calls `doctor` (stretch)

### Phase 8 — Verification & closure

- [ ] **8.1** `.\scripts\signoff.ps1` green (full)
- [ ] **8.2** Manual: `poetry run figma-flutter generate` sign_in → `demo_app` analyze clean
- [ ] **8.3** Manual: live Figma smoke (record URL in PR description, not in repo)
- [ ] **8.4** S9 review: no screen-specific hacks in `src/` (universal-codegen rule)
- [ ] **8.5** Mark DoD checkboxes in § S1

---

## Commands reference

```powershell
# Dev
poetry install --with dev
.\scripts\bootstrap.ps1
poetry run figma-flutter doctor

# AST build (maintainers)
bash tools/build_sidecars.sh

# Golden baselines (all manifest screens)
poetry run python scripts/generate_fixture_goldens.py --golden-runtime docker
# or host when FIGMA_FLUTTER_SDK is set:
poetry run python scripts/generate_fixture_goldens.py --golden-runtime host

# Combat renders from generate (visual refine): logs/renders/{timestamp}-{run_id}/

# Signoff
.\scripts\signoff.ps1

# Tests
poetry run pytest -q -m "not live_figma"
poetry run pytest tests/test_ast_sidecar.py -v
poetry run pytest tests/test_geometry_music_v2_ru_dirty.py -v
```

---

## Parallel agent roster (optional)

| Agent | Stream | First task |
|-------|--------|------------|
| Compiler | A | 2.1–2.4 |
| Parser | B | 1.1–1.5, 3.1–3.3 |
| Infra | C | 4.1–4.3 |
| Vision | D | 5.1–5.3 (after M1) |
| CLI | E | 7.1–7.3 (after M3) |

**Integration owner** merges at M1→M2→M3→M4; resolves conflicts in `planned_dart.py`, `config.py`, `signoff.ps1`.

---

## S6 entry criteria

- [x] S4 concept approved (variant 3)
- [x] S5 plan file exists (`docs/projects/ast-modernization/ast-modernization.md`)
- [x] User command: **РАБОТА!** / S6 started (2026-05-27)

**Stop rule:** If AST parity tests fail after 4h on a rule — log in plan § Risk, fallback flag `runtime.use_ast_sidecar: false` only in dev, not for merge.
