# Artifact identity contract (Program 10 P0-3)

| Artifact | Identity fields | Consumers | Gaps |
|----------|-----------------|-------------|------|
| `llm_validated.json` | `cleanTreeHash`, `cleanRootFigmaId`, `parserVersion`, `irSchemaVersion`, `generationConfigFingerprintVersion`, `generationConfigHash`, `irCacheFingerprintVersion` | `load_cached_ir_llm_outcome`, wizard IR-offline | enforce path gated by `FIGMA_IR_CACHE_POLICY` |
| `processed.json` | `parserVersion`, clean tree body hash | dump prefetch, incremental | generation config not stamped on processed |
| `pre_emit.json` | `emitterVersion`, IR body | incremental sync, determinism gate | run id paths excluded from hash |
| `provenance.json` | `emitterVersion`, mutation ledger | debug triage | not part of cache invalidation key |
| `run.meta.json` | `runMetaSchemaVersion`, `pipeline_run_id`, `clean_tree_hash`, `generation_config_hash`, `cached_ir_verdict` | Run Gate, opencode | stale plan.dart warning partial |
| `ir-cache-compatibility-report.json` | `verdict`, `missingIdentityFields`, `mismatchedIdentityFields` | shadow diagnostics | advisory until enforce PR |

**Policy:** missing identity stamps on cached IR → `legacy_unknown` in shadow; enforce regenerates IR when pipeline available.
