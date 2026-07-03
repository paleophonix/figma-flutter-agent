# EPIC 6.1 — Corpus oracle hardening

> Status: **in progress** (post W0 review, 2026-06-12)

Parent: [epic-6-corpus-oracle.md](epic-6-corpus-oracle.md). Foundation: [epic-6-w0.md](epic-6-w0.md).

## Verdict on W0

```text
ACCEPT as E6.W0 / S6 foundation
NOT complete E6
```

## E6.1 DoD

| # | Item | Status |
| --- | --- | --- |
| 1 | Corpus >=25 total, 8–12 `strict_pixel_blocking` | pending (W1 corpus wave) |
| 2 | Promotion candidates tied to classified kind on fixture | done |
| 3 | `text_bounds_delta` uses runtime `figma_key_rects` mapper | done |
| 4 | Skipped blocking fails signoff unless `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` | done |
| 5 | `full_corpus_passed` vs `blocking_passed` split in reports | done |

## Env

| Variable | Effect |
| --- | --- |
| `FIGMA_CORPUS_ORACLE_SIGNOFF=0` | Skip entire corpus-oracle step in signoff |
| `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` | Allow exit 0 when all blocking screens skipped (local only) |

## Remaining for complete E6

- Corpus growth to >=25 screens (see epic-6 W1 wave)
- S6.1.W1 real-design W1 integration corpus
- Metamorphic / affine / screen-level semantic no-op oracles (W3)
