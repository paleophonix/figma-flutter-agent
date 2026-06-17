---
name: diagnose
description: >-
  Diagnosis for pipeline, layout, IR, semantic, contract, emitter failures.
  Inspects processed `.repair/debug` artifacts, maps symptoms to laws, builds
  a repair queue. Read-only — no code edits.
---

# Diagnose skill (OpenCode / auto-repair)

Synced from `.claude/skills/diagnose/SKILL.md` for headless repair diagnosticians.

## Artifact root

Read **only** the copied bundle:

```text
.repair/debug/<project>/<feature>/
```

Hot read order:

```text
last.log → dart-errors.json → processed.json → pre_emit.json → semantics.json
```

Do **not** use deprecated agent `logs/` paths.

## Rules

- Diagnosis only — no production code changes.
- Map every symptom to a **named law** and **compiler layer** (`parser`, `ir`, `emitter`, etc.).
- No screen-specific, figmaId-specific, or text-value patches.
- Output structured JSON when prompted.

## Output (diagnostician role)

```json
{
  "root_cause": "...",
  "confidence": 0.0,
  "recommended_law": "...",
  "escalate": false
}
```

Full doctrine: `.claude/prompts/debug-common.md` in the agent repo.
