# M2 closure record (gate for M3 authority switches)

**Status:** `PENDING` — required before Phase 4 production authority merges.

## Required fields

| Field | Value |
|-------|-------|
| `M2_FINAL_COMMIT` | _(unset)_ |
| `CI_GREEN` | _(unset)_ |
| `ACCEPTANCE_REPORT` | [m2-acceptance-report.md](m2-acceptance-report.md) |
| `SIGNED_OFF_BY` | _(unset)_ |
| `SIGNED_OFF_AT` | _(unset)_ |

## Blocked until closure

- 04-P0-2b DefinitionKey authority
- 04-P0-3b blocking `ExtractionBijectionError`
- 06-P0-1d per-route resolver migrations (enforce mode)
- M3 final signoff

## Allowed before closure

Contracts, inventories, additive models, shadow/report-only diagnostics, tests, corpus cases.

## Authority flags (dev)

Set `FIGMA_M3_AUTHORITY_ENABLED=1` only after this record is `CLOSED` with green CI on `M2_FINAL_COMMIT`.
