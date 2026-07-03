# E5-1 Debt Budget Governance Draft

## Goal
Define the first non-blocking governance schema for baseline-driven debt gates so reports can show trust progress, not only whether known fingerprint debt failed to grow.

## Scope
Included:
- Document a milestone-relative debt budget schema.
- Cover the initial gate families: `settings_purity`, `regex_dart_surgery`, and `semantics_legacy_burndown`.
- Define per-gate `current`, `target`, `delta`, `deadline`, and `owner` reporting fields.
- Keep the first pass non-blocking and schema/reporting-only.

Excluded:
- Runtime YAML configuration.
- Fixture or generated report files as the governance source of truth.
- Blocking budget enforcement.
- Tier-aware pass/fail rewrites.
- Corpus quota CI.
- Calendar deadlines.

## Technical Plan
1. Use this document as the first source-of-truth draft for E5 debt budget reporting.
2. Define milestone-relative deadlines: M0 current baseline snapshot, M1 first reduction after E0 green, M2 visible reduction, M3 target-zero or explicitly approved residual debt.
3. Define a common report shape for each budgeted gate: `gate`, `current`, `target`, `delta`, `deadline`, `owner`, `status`, and `notes`.
4. Draft initial budgets for `settings_purity`, `regex_dart_surgery`, and `semantics_legacy_burndown` without guessing numeric counts before discovery.
5. Leave enforcement advisory-only until later E5 slices decide runtime config and CI behavior.

## Checklist
1. [x] Define shared debt budget schema fields.
2. [x] Draft `settings_purity` milestone budget.
3. [x] Draft `regex_dart_surgery` milestone budget.
4. [x] Draft `semantics_legacy_burndown` milestone budget.
5. [x] Define non-blocking report status semantics for E5-1.

## Acceptance Criteria
- Governance budgets have an explicit schema separate from lint baselines and generated reports.
- Initial budget drafts exist for all three requested gates.
- Milestones are relative (`M0` through `M3`), not calendar dates.
- The draft does not enable blocking CI behavior.
- The draft does not make fixtures or output reports the governance source of truth.

## Milestones
- `M0`: Current baseline snapshot.
- `M1`: First reduction after E0 green.
- `M2`: Visible reduction.
- `M3`: Target-zero or explicitly approved residual debt.

## Shared Schema
```yaml
budget:
  gate: string
  current: TBD_FROM_BASELINE
  target:
    M1: string
    M2: string
    M3: string
  delta: TBD_FROM_REPORT
  owner: string
  deadline: milestone:M1|milestone:M2|milestone:M3
  status: advisory
  notes: string
```

## Initial Gate Budgets
```yaml
budget:
  gate: settings_purity
  current: TBD_FROM_BASELINE
  target:
    M1: no new entries; materialize.py leak removed
    M2: <= 50% of M0
    M3: 0
  delta: TBD_FROM_REPORT
  owner: Branch A
  deadline: milestone:M3
  status: advisory
  notes: First pass is schema/reporting only; no blocking enforcement.
```

```yaml
budget:
  gate: regex_dart_surgery
  current: TBD_FROM_BASELINE
  target:
    M1: no new entries
    M2: reduce by at least 30%
    M3: target 0 or approved allowlist with owner
  delta: TBD_FROM_REPORT
  owner: Branch A
  deadline: milestone:M3
  status: advisory
  notes: First pass is schema/reporting only; no blocking enforcement.
```

```yaml
budget:
  gate: semantics_legacy_burndown
  current: TBD_FROM_BASELINE
  target:
    M1: no new text/name production effects
    M2: migrate critical callsites to SemanticEvidence
    M3: remaining legacy entries require explicit owner/deadline
  delta: TBD_FROM_REPORT
  owner: Branch B
  deadline: milestone:M3
  status: advisory
  notes: First pass is schema/reporting only; no blocking enforcement.
```

## Report Shape
```yaml
governanceDebtBudget:
  gate: string
  current: integer
  target: string | integer
  delta: string | integer
  deadline: string
  owner: string
  status: advisory | on_track | behind_target
  blocking: false
```

## Non-Blocking Status Semantics
- `advisory`: budget exists, but enforcement is not active.
- `on_track`: current report satisfies the milestone target once reporting is implemented.
- `behind_target`: current report misses the milestone target once reporting is implemented.
- `blocking`: always `false` for E5-1.
