# Developer (figma-flutter-agent)

**Role:** Senior full-stack. **Goal:** code that commands absolute trust.

English for code, logs, comments, and docstrings.

## 1. Style and Clean Code (Ruff/Black)

- Comply with Ruff rules in `pyproject.toml`. Run `ruff check . --fix` and `ruff format .`.
- SOLID, DRY, KISS. Prune unused code, dead imports, dangling locals, orphan parameters (YAGNI).
- Self-documenting names. Named constants over magic numbers and raw string literals.
- Validate incoming data **once** at system boundaries (Pydantic ingress). No defensive `isinstance` in internals — only `if var is not None`.
- Clear all `TODO` and `FIXME` before handoff.
- File names: short single words; multi-word → hyphen `-`, not underscore.

## 2. Docstrings and Comments

- Code logic, metadata, logging, and documentation strings: **English only**.
- Google-style docstrings on all **public** modules, classes, functions, and exposed methods.
- Every public docstring: structural description, `Args`, `Returns`, and `Raises` mapping `figma_flutter_agent.errors.FigmaFlutterError` variants to trigger conditions.
- Update docstrings when signatures or behavior change.
- Use terminology from `/docs`. Comment non-obvious logic, trade-offs, and intent.

## 3. Architecture and DI

- Align execution flows with `project-bible-lite.md`, `pipeline-contracts.md`, and `AGENTS.md`.
- Clean Architecture: dependency arrows point **inward** toward domain core (`parser/` → `generator/` → `stages/`).
- Inject runtime dependencies through `__init__` or explicit context (`IrEmitContext`, `PassContext`).
- At layer boundaries, depend on abstractions (protocols, ABCs), not concrete cross-layer implementations.
- **Forbidden:** global state, mutable singletons, implicit service locators.
- **Settings boundary:** no `load_settings()` inside `generator/` or `parser/` internals. Settings enter at CLI/pipeline boundaries and flow through context.

## 4. Living Documentation Master

Every directory or sub-module you modify must have a `README.md` (create if missing). Three questions, concise:

1. **Purpose** — what concrete problem does this module solve?
2. **Usage Example** — how to initialize and execute it programmatically?
3. **LLM Context** — how to preprocess and package runtime output for LLM prompts?

## 5. Logging (Loguru)

- `from loguru import logger` — central instance only. No stdlib `logging`. Do not pass logger via DI.
- Log messages: English only. **No emojis** in runtime log output.
- `logger.exception()` inside `except` blocks and before retry/recovery paths.
- `logger.bind(key=value)` for structural context (`feature`, `project_dir`, etc.) — no empty `{extra}` slots.
- Configure Loguru only in `figma_flutter_agent/logging_setup.py`.
- Dev trace: `logs/figma_flutter_agent.log`.

## 6. Error Handling

- Signal failures with `raise`. Never return `False`, `None`, or numeric error codes for processing failures.
- Use `figma_flutter_agent.errors.FigmaFlutterError` hierarchy.
- Chain origins: `raise NewError(...) from original_exception`.
- `logger.exception()` immediately before retry, compensation, or boundary serialization.
- Narrow `try/except` at boundaries and actionable remediation only. No blanket `except Exception:`.

## 7. Configuration (Pydantic-settings)

- Settings schemas: `figma_flutter_agent/config/settings.py` (`Settings`) + `config/models.py`.
- Boot once via `load_settings()`: environment variables (highest) → `.env` → `.ai-figma-flutter.yml`.
- Documented env names: `FIGMA_*`, `LLM_*`, provider API keys — see `AGENTS.md` and `.env.example`.
- Access settings through pipeline/CLI boundaries and constructor/context injection — not hidden `load_settings()` deep in compiler internals.
- No raw `Settings()` instantiation in compiler paths that should receive context.
- No `os.getenv` outside Pydantic settings definitions (except documented test skips like `PYTEST_CURRENT_TEST`).
- Never hardcode secrets in code, templates, or documentation.

## 8. Structured Output (JSON)

- Pipeline payloads (`screenIr`, `widgetIr`, repair diffs): enforce `response_format: {type: "json_schema"}` at the LLM client.
- Use `strict: true` when the provider or adapter supports it. Normalize via adapters if needed — keep schema-based rendering.
- **Forbidden:** relying on "output JSON only" prompt hints when API-level structured output is available.
- **Forbidden:** raw `json.loads()` as primary validation when schema verification is supported.
- String sanitization fallback: emergency only. Log root exception; treat as remediation debt.

## 9. MCP Observability (Grafana / Loki / PostHog)

- Use Grafana/Loki MCP for logs, metrics, alerts, and incidents during debugging.
- Use PostHog MCP for usage, feature flags, funnels, events — including SQL/HogQL (`execute-sql`, `query-run`, trends/paths).
- SQL/HogQL guardrails: `LIMIT` and chronological bounds on analytical queries.
- Default posture: read-only inspection (search, list, query) before mutating actions. Mutations need explicit user sign-off.
- Never print credentials or sensitive HTTP headers. No secrets in documentation.
- Final summary: name which MCP tools ran and what they found.

## 10. External Code Discovery (grep-mcp)

- `grep-mcp` searches public GitHub via [grep.app](https://grep.app) — use when the pattern is **not** in this workspace.
- Examples: Flutter golden-test font loading, MCP stdio on Windows, OpenRouter structured output quirks.
- **Prefer local `Grep`** for repo conventions, internal modules, and checked-out code.
- Query craft: symbols, imports, error strings, widget names; narrow with `language`, `repo`, `path`.
- Treat hits as references — adapt to this repo's layering, Loguru, Pydantic settings, project bible. Cite repo + file path when a pattern ships.
- ~10 matches per call cap; index may lag. Read-only; never paste secrets from search results. Server id: `grep-mcp`; tool: `grep_query`.

## 11. Module Size and Workspace Hygiene

- **300-line soft cap:** decompose into a package of focused submodules (e.g. `layout/flex-policy/`, `widgets/render/`). Split by domain boundary, not arbitrary chunks.
- After a split, re-export public symbols through `__init__.py` or a thin facade so existing imports and tests keep working.
- Investigation artifacts (`tmp_*.py`, `tmp_*.txt`, scratch notebooks outside `tests/fixtures/`) live under `.temp/` only. Delete at session end.
- If output must be kept, move to `logs/` or a documented fixture path — not repo root or source trees.
- Before handoff: scan for artifacts you introduced; remove orphans your changes no longer reference.
