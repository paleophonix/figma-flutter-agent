# Milestone 2 acceptance report

**Date:** 2026-07-03  
**Baseline:** `5f03c758` (pre-M2)  
**Implementation commits:** `6511a921` (P0 02+03), `75114255` (food_menu_2 canary + minor fixes)  
**Runner:** local Windows, `poetry run`

## 1. Targeted pytest (reviewer bundle)

```powershell
poetry run pytest `
  tests/test_conservation_registry.py `
  tests/test_conservation_invariants.py `
  tests/test_extracted_ir_terminal_law.py `
  tests/test_policy_decision.py `
  tests/test_semantics_evidence_specs.py `
  tests/test_shadow_classifier_inventory.py `
  tests/test_cp_post_classify.py `
  tests/test_ir_layout_passes.py `
  tests/test_pass_contract.py -q
```

| Result | Detail |
|--------|--------|
| **PASS** | **57 passed** in ~8s |
| Log | `.temp/m2-acceptance-pytest.txt` |

## 2. Defects validate

```powershell
poetry run figma-flutter defects validate
```

| Result | Detail |
|--------|--------|
| **PASS** | `defect corpus: valid` |
| Log | `.temp/m2-acceptance-defects.txt` |

## 3. Signoff / extended gates

### 3a. `demo-signoff --strict --signoff-gates`

| Result | Detail |
|--------|--------|
| **PASS** | exit 0 (~76s) |
| Log | `.temp/m2-demo-signoff.txt` |
| Fixtures | 5 PASS (`figma_node_sample`, carousel, tabs, bottom_nav, grid) |

### 3b. Full `.\scripts\signoff.ps1`

Run with `FIGMA_GEOMETRY_SIGNOFF=0`, `FIGMA_CORPUS_ORACLE_SIGNOFF=0` (docker oracle optional on this host).

| Result | Classification |
|--------|----------------|
| **FAIL** at `ruff check .` | **pre-existing failure** — files **not** in M2 diff (`5f03c758..HEAD`) |

Ruff findings (unrelated to 02+03 P0):

- `src/figma_flutter_agent/generator/layout/widgets/emit/containers.py` — I001 import sort
- `src/figma_flutter_agent/generator/layout/widgets/emit/text.py` — SIM114
- `src/figma_flutter_agent/schemas/__init__.py` — I001
- `tests/test_dev_run.py` — F401, I001

**Not a new M2 regression.** Fix = separate hygiene PR (`ruff check . --fix`).

### 3c. `fixture-geometry-check` (optional signoff step)

| Result | Classification |
|--------|----------------|
| **FAIL** exit 1 | **environment failure** — all 10 screens **SKIP** (`Flutter SDK unavailable?` / docker golden test path missing) |

Not attributable to conservation/registry/policy changes.

## 4. Fleet regeneration (offline manifest screens)

Source: `tests/fixtures/screens.yaml` (10 reproducible layout JSON screens).

### 4a. IR validate (`parse → default IR → guards → validate`)

```powershell
poetry run figma-flutter fixture-ir-validate
```

| screen | generation | conservation | semantic | dart |
|--------|------------|--------------|----------|------|
| sign_up_and_sign_in | ok | n/a | n/a | n/a |
| reminders | ok | | | |
| music_v2 | ok | | | |
| music_v2_ru_dirty | ok | | | |
| bounded_order_card | ok | | | |
| consent_checkbox | ok | | | |
| flex_summary_row | ok | | | |
| prefilled_input | ok | | | |
| deep_nesting | ok | | | |
| variant_topology | ok | | | |

**10/10 PASS** — log: `.temp/m2-fleet-ir-validate.txt`

### 4b. Classify + post-classify conservation

Script: `.temp/m2_fleet_classify.py` (classify → `run_cp_post_classify`).

| screen | generation | conservation | semantic diff | unexpected |
|--------|------------|--------------|---------------|------------|
| all 10 | ok | pass | classify+post_classify ok | none |

**10/10 PASS** — log: `.temp/m2-fleet-classify.txt`, JSON: `.temp/m2-fleet-classify.json`

### 4c. Semantics W1 gate

```powershell
poetry run figma-flutter semantics corpus-gate
```

| Result |
|--------|
| **PASS** precision=1.000 recall=1.000 blocker_fp=0 tree_fp=0 |

### 4d. Dart emit / golden

Not run fleet-wide on this host (docker golden capture unavailable). Covered partially by **demo-signoff** (5 strict demo fixtures, PASS).

## 5. Debug artifacts (`food_menu_2`)

| Commit | `.debug/screen/limbo/food_menu_2` changes |
|--------|-------------------------------------------|
| `6511a921` | `ai_ux.json`, `llm_parsed.json`, `llm_validated.json`, `widget_enrich.json` (large LLM IR drift) |
| `75114255` | `llm_parsed.json`, `reusable_candidates.json`, `semantic_context.json` + small `checkpoints.py` / `expression.py` tweaks |

**Recommendation:** treat as **accidental working state**, not M2 evidence.

- **Option A (preferred):** revert `.debug/**` from both commits in a follow-up; keep P0 code-only on `main`.
- **Option B:** if intentional canary — separate commit `chore(debug): food_menu_2 canary run` with model/prompt/config revision notes.

M2 acceptance **does not depend** on `food_menu_2` debug dumps.

## 6. Verdict

| Gate | Status |
|------|--------|
| Targeted M2 pytest | **PASS** |
| `defects validate` | **PASS** |
| `demo-signoff --strict` | **PASS** |
| Fleet IR + classify/conservation (10 screens) | **PASS** |
| Semantics W1 gate | **PASS** |
| Full `signoff.ps1` | **BLOCKED** — pre-existing ruff debt (unrelated files) |
| Fleet geometry/golden | **BLOCKED** — environment (docker/SDK) |
| `food_menu_2` debug in git | **OPEN** — hygiene / canary documentation |

### Milestone 2 acceptance (conditional)

**Program 02 P0** and **Program 03 P0** — **functionally complete** with published local evidence above.

**Milestone 2 final stamp** remains open until:

1. CI publishes green checks on `6511a921` (or ruff hygiene fix lands), and  
2. `food_menu_2` debug policy resolved (revert or named canary).

**Safe to proceed to M2.1 / P1** on code architecture; parallel track: ruff hygiene PR + debug cleanup.
