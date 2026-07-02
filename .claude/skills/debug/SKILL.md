---
name: debug
description: >-
  General debugging for control plane, Discord, worker/ARQ, Postgres/Redis,
  infra/env, runtime imports, and CLI startup — not screen/compiler layout.
  Pairs with /fix only. Use for /debug or "что сломалось" outside the
  diagnose-repair compiler flow.
disable-model-invocation: false
---

@.claude/prompts/debug-common.md

# Debug Skill — general triage (pairs with `/fix` only)

Use **`/debug`** for failures **outside** the screen/compiler pipeline.

**Separate flow (do not mix):**

```text
/debug → /fix           control plane, infra, imports, CLI startup
/diagnose → /repair     screen layout, IR, emitter, golden, .debug artifacts
```

If the problem is wrong layout, missing widgets, analyzer on generated screen Dart,
golden diff, or law-level compiler behavior — **stop**. That is **`/diagnose`**, not `/debug`.

## Default mode

**Triage-only** unless the user asked to fix (`/fix`, "почини").

- Do not edit code in debug-only mode.
- Do not hand-edit generated Dart in Flutter projects.

---

# Step 0 — Classify domain (in scope)

| Domain | Typical symptoms | Primary evidence |
| ------ | ---------------- | ---------------- |
| **A. Control plane** | Discord slash fails, job stuck, no preview, webhook | control-panel logs, Postgres jobs, Redis, worker |
| **B. Infra / env** | Process won't start, DB password, Redis down | `.env`, `.discord-bot.yml`, `docker ps`, traceback |
| **C. Runtime / import** | `ImportError`, `CommandInvokeError`, crash before pipeline | Python traceback, import chain |
| **D. CLI / entry** | CLI won't start, wizard menu crash, fetch/auth before IR | `last.log` head, `logs/figma_flutter_agent.log` |
| **F. Observability** | Metrics/PostHog/Loki wiring | global logs, `/metrics`, config |

**Out of scope for this skill:** parse/classification/IR/emitter/layout/golden/analyzer on
a specific screen — use **`/diagnose`**.

---

# Step 1 — Resolve context

```text
What failed? (Discord /generate, worker, CLI, docker, import)
When? (fresh vs stale)
Control plane up? (panel + worker)
Env/config paths: .env, .discord-bot.yml
```

For CLI entry failures, read only enough `.debug/.../last.log` to see **which stage
aborted before screen work** — do not deep-read IR/layout artifacts here.

---

# Step 2 — Domain hot paths

## A. Control plane + Discord

```text
1. Terminal output (panel + worker)
2. GET http://127.0.0.1:8787/health and /ready
3. .env — DISCORD_BOT_TOKEN, FIGMA_CP_*, DISCORD_BOT_INTERNAL_SECRET
4. .discord-bot.yml — discord.enabled, guild_ids, sync_joined_guilds
5. Postgres generation_jobs / repair_jobs
6. Redis (FIGMA_CP_REDIS_URL)
```

## B. Infra / env

```text
1. Startup traceback (first exception)
2. .env vs examples
3. docker ps
4. database.mode + FIGMA_CP_DATABASE_URL
```

## C. Runtime / import

```text
1. Full traceback — innermost cause
2. Module cycle A → B → A
3. Grep importers of failing symbol
4. Lazy import inside handler vs module-level
```

Proof: `poetry run python -c "import …"`.

## D. CLI / entry

```text
1. logs/figma_flutter_agent.log
2. .debug/.../last.log — first failing stage only
3. CLI flags, tokens, project-dir existence
```

If log shows IR/layout/emitter/analyzer failure on a screen → **out of scope**; user needs `/diagnose`.

## F. Observability

```text
1. logs/figma_flutter_agent.log
2. metrics endpoint / PostHog config
```

---

# Step 3 — Evidence rules

Every claim needs: source path, freshness, expected vs actual, responsible layer.

---

# Step 4 — Output: DEBUG TRIAGE REPORT

```text
DEBUG TRIAGE REPORT

Trigger:
Domain: A|B|C|D|F
Freshness:

Symptoms:
Evidence:
Root cause:
Responsible layer:

Next action:
  - RUN /fix (implement)
  - USER ACTION (env, docker, Discord)
  - OUT OF SCOPE → user should run /diagnose (screen/compiler)

Queue preview:
  R1 [P0]: …

Blocked by:
```

---

# Step 5 — Fix gate

`/debug` alone does **not** change code.

Implementation belongs to **`/fix`** in the same flow (`/debug` → `/fix`).

Do not route to `/diagnose` or `/repair` from this skill.

---

# Quick reference — local control plane

```text
scripts/start-control-plane.ps1  → Redis, worker, API :8787
.env + .discord-bot.yml
Log: "Discord slash commands synced to joined guilds: [...]"
```
