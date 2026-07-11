# Agent prompts

Rules: `.cursor/rules/`. Skills: `.cursor/skills/`.

**Order:** `pipeline-architecture.mdc` — phases strictly in order, no mixing. Every phase skill is a numbered **protocol**: steps in order, each with a Check; a failed Check stops the phase.

**Gates are mechanical:** flag in the artifact **+** `node .agent/tools/check.mjs --phase <phase>` exit 0. No capture/diff tool — inspect compares design vs built Dart, plus a user screenshot when provided.

**Spec adherence:** `screen_contract.json` (ТЗ) — layout writes, plan covers, inspect verifies (`spec-contract.mdc`).

**Artifact per phase:** one JSON + one RU chat report. No `*_brief.md`.

Project catalogs: `widget_catalog.json`, `token_catalog.json` — see `widget-reuse.mdc`, `token-reuse.mdc`. Promoted lessons: `rules/lessons.mdc`.

| Skill | JSON |
|-------|------|
| layout / plan / build / inspect / debug / fix | see `pipeline-architecture.mdc` |
| autobuild / autofix | same phase JSONs, one summary report |
| batch | autobuild over `.agent/screens.yaml`, one ОТЧЁТ: ПАКЕТ |

`AGENT_FEATURE` in `.env`.
