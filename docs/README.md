# Documentation

Product feature map: [README.md](../README.md). Agent context: [AGENTS.md](../AGENTS.md). Layout law: [.cursor/rules/docs-layout.mdc](../.cursor/rules/docs-layout.mdc).

## Layout convention

```
docs/
  <category>/                    # product, reference, spec, projects, …
    YY-MM-DD-name.md             # single-file doc
    YY-MM-DD-project/            # multi-file project (date = earliest file)
      file.md                    # no date prefix inside project folder
```

## Product

| Doc | Contents |
|-----|----------|
| [product/26-07-01-product-overview.ru.md](product/26-07-01-product-overview.ru.md) | Обзор для продакта/дизайна (RU) |
| [product/26-06-07-assessment.md](product/26-06-07-assessment.md) | Product assessment |
| [product/26-06-08-project-evaluation.md](product/26-06-08-project-evaluation.md) | Project evaluation |

## Reference (engineering)

| Doc | Contents |
|-----|----------|
| [reference/26-07-01-engineering-reference/cli.md](reference/26-07-01-engineering-reference/cli.md) | CLI commands, batch dump scopes, flags |
| [reference/26-07-01-engineering-reference/debug-artifacts.md](reference/26-07-01-engineering-reference/debug-artifacts.md) | `.debug/screen/` layout, triage read order |
| [reference/26-07-01-engineering-reference/development.md](reference/26-07-01-engineering-reference/development.md) | Tests, signoff, generation profiles, CI smoke |
| [reference/26-07-01-engineering-reference/technical-notes.md](reference/26-07-01-engineering-reference/technical-notes.md) | Limitations, sync, LLM providers, spec interpretation |

## Spec

| Doc | Contents |
|-----|----------|
| [spec/26-05-24-product-spec/spec.md](spec/26-05-24-product-spec/spec.md) | Product specification |
| [spec/26-05-24-product-spec/spec-amendments.md](spec/26-05-24-product-spec/spec-amendments.md) | Spec amendments |
| [spec/26-05-24-product-spec/limitations.md](spec/26-05-24-product-spec/limitations.md) | Known limitations |
| [spec/26-05-25-ide-setup.md](spec/26-05-25-ide-setup.md) | IDE / Cursor setup |

## Coverage & theory

| Doc | Contents |
|-----|----------|
| [coverage/26-05-31-cupertino-coverage.md](coverage/26-05-31-cupertino-coverage.md) | Cupertino widget coverage |
| [coverage/26-06-12-figma-feature-coverage.md](coverage/26-06-12-figma-feature-coverage.md) | Figma feature coverage |
| [theory/26-06-24-universal-translation-theory.md](theory/26-06-24-universal-translation-theory.md) | Translation theory |
| [theory/26-07-02-widget-extraction-policy.md](theory/26-07-02-widget-extraction-policy.md) | Widget extraction policy |

## Audit

| Doc | Contents |
|-----|----------|
| [audit/26-06-13-pipeline-audit/](audit/26-06-13-pipeline-audit/) | Systemic pipeline audit (CLI: `figma-flutter audit all`) |

## Refactor program

| Doc | Contents |
|-----|----------|
| [refactor/26-06-06-compiler-refactor/](refactor/26-06-06-compiler-refactor/) | Compiler refactor specs, contracts, generated ratchets |

## Planning

| Doc | Contents |
|-----|----------|
| [planning/26-05-22-plan.md](planning/26-05-22-plan.md) | Early product plan |
| [planning/26-05-24-roadmap-10-10.md](planning/26-05-24-roadmap-10-10.md) | 10/10 roadmap |
| [planning/26-05-28-llm-prompts.md](planning/26-05-28-llm-prompts.md) | LLM prompt notes |
| [planning/26-06-06-roadmap-p3-epics.md](planning/26-06-06-roadmap-p3-epics.md) | P3 epics |

## Projects

Implementation epics live under [projects/](projects/). Naming: `YY-MM-DD-<slug>.md` (one file) or `YY-MM-DD-<slug>/` (folder).

Notable multi-file projects:

| Folder | Topic |
|--------|-------|
| [projects/26-06-04-core-audit/](projects/26-06-04-core-audit/) | Core audit & geometry TZ |
| [projects/26-06-11-semantic-core/](projects/26-06-11-semantic-core/) | Semantic core epics |
| [projects/26-06-13-codex-hardening/](projects/26-06-13-codex-hardening/) | Codex hardening & layout laws |
| [projects/26-06-18-repair-opencode/](projects/26-06-18-repair-opencode/) | OpenCode repair pipeline |
| [projects/26-06-18-observability/](projects/26-06-18-observability/) | Prometheus metrics |

## Other categories

| Category | Contents |
|----------|----------|
| [research/](research/) | Research notes |
| [governance/](governance/) | Debt budgets |
| [architecture/](architecture/) | Module architecture |
| [rules/](rules/) | Archived agent rule snapshots |
| [sessions/](sessions/) | Debug session logs |

## Repo docs (outside `docs/`)

| Doc | Contents |
|-----|----------|
| [../scripts/README.md](../scripts/README.md) | Signoff scripts, lint gates, E2E helper |
| [../tests/README.md](../tests/README.md) | Pytest markers, manual E2E acceptance |
| [../src/control_panel/README.md](../src/control_panel/README.md) | Control panel setup |
