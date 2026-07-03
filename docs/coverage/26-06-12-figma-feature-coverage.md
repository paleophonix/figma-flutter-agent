# Figma feature coverage (E5.W1)

W1 semantic kinds only. W2+ rows are planned in follow-up waves.

| Figma feature | parse | classify | emit | oracle | fidelity_tier | fixture_ids |
| --- | --- | --- | --- | --- | --- | --- |
| Button filled | lossless | native | native_verified template | corpus | native_verified | btn-filled-1, btn-filled-2, btn-filled-3 |
| Button outlined | lossless | native | native_unverified template | corpus | native_unverified | btn-outlined-1, btn-outlined-2, btn-outlined-3 |
| Button text | lossless | native | native_unverified template | corpus | native_unverified | btn-text-1, btn-text-2, btn-text-3 |
| Input text field | lossless | native | native_unverified template | corpus | native_unverified | input-1, input-2, input-3 |
| Chip choice row | lossless | native | native_verified template | corpus | native_verified | chip-row, chip-row-numeric, chip-row-compact |
| Container card | lossless | native | native_unverified template | corpus | native_unverified | card-1, card-2, card-3 |
| Container list tile | lossless | native | native_unverified template | corpus | native_unverified | tile-1, tile-2, tile-3 |
| Technical divider | lossless | native | native_unverified template | corpus | native_unverified | divider-1, divider-2, divider-3 |

Blocker-negative traps: see `tests/fixtures/layouts/semantics/manifest.yaml` → `w1.blocker_negatives`.
