# Карта проекта figma-flutter-agent

Построено командой `tree /F /A src\figma_flutter_agent` (Windows), с вырезанными `__pycache__`, `.pyc` и свёрткой периферии.

**Охват:** пакет `src/figma_flutter_agent/` — ядро генерации.  
**Свёрнуто до модуля:** `dev/`, `wizard/`, `batch/`, `audit/`, `observability/`, `tools/`, `preview/`, `src/control_panel/`.

---

## Поток данных (сверху вниз)

```text
cli/ → pipeline/run/ → stages/ → [figma, parser, llm, generator, assets, fonts, validation, sync]
                              ↓
                    .debug/screen/ + logs/
```

---

## Дерево (generation core, урезанное)

```text
src/figma_flutter_agent/
├── errors.py, logging_setup.py, pipeline_context.py, redaction.py, render_log.py, dart_error_log.py
├── config/
├── schemas/
├── cli/
├── figma/
├── parser/
│   ├── *.py (корень)
│   ├── dedup/
│   ├── boundaries/
│   ├── tokens/
│   ├── interaction/
│   ├── layout/
│   ├── semantics/
│   │   ├── detectors/
│   │   └── signals/
│   └── annotations/
├── assets/
├── fonts/
├── llm/
│   ├── clients/
│   ├── prompts/
│   └── repair_scope/
├── pipeline/
│   └── run/
├── stages/
│   ├── llm_repair/
│   └── visual_refine/
├── generator/
│   ├── templates/
│   ├── ir/
│   │   ├── passes/
│   │   ├── validate/
│   │   ├── fidelity/
│   │   ├── contracts/
│   │   ├── presence/
│   │   └── data/
│   ├── layout/
│   │   ├── flex_policy/
│   │   ├── style/
│   │   ├── navigation/
│   │   ├── widgets/
│   │   │   ├── emit/
│   │   │   ├── input/
│   │   │   └── button/
│   │   └── interactive/
│   ├── geometry/
│   │   └── invariants/
│   ├── planner/
│   ├── planned/reconcile/
│   ├── widget_extraction/
│   ├── dart/
│   │   ├── postprocess/
│   │   ├── llm_codegen/
│   │   └── project_validation/
│   ├── subtree/, background/, figma_anchor/, variant/, rendering/, checks/, writing/
│   └── *.py (корень generator)
├── validation/
│   ├── golden_capture/
│   ├── oracle/
│   ├── pixel/
│   └── spec23/
├── sync/
├── debug/
├── fixtures/
│
│  ─── свёрнуто (не в дереве) ───
├── dev/          # IDE wizard, opencode, import helpers
├── wizard/       # legacy wizard entrypoints
├── batch/        # batch file dumps
├── audit/        # predicate overlap, docs for reviewers
├── observability/# run id, stage timing
├── tools/        # AST sidecar wrappers, process utils
└── preview/      # preview server helpers

src/control_panel/   # FastAPI + Discord + ARQ (вне figma_flutter_agent)
```

---

## Корень пакета `figma_flutter_agent/`

| Файл | Назначение |
|------|------------|
| `errors.py` | Иерархия `FigmaFlutterError` / `GenerationError`; sanitize API messages |
| `logging_setup.py` | Единственная точка конфигурации Loguru |
| `pipeline_context.py` | Mutable state прогона: clean tree, tokens, generations, planned files |
| `redaction.py` | Редакция секретов в логах и ошибках |
| `render_log.py` | Телеметрия render-стадий |
| `dart_error_log.py` | Запись `dart-errors.json` в `.debug` |
| `README.md` | Краткая module map пакета |

---

## `config/` — настройки (граница pipeline)

| Файл | Назначение |
|------|------------|
| `settings.py` | Корневой `Settings` (Pydantic): env + YAML merge |
| `models.py` | Вложенные схемы: flutter, generation, runtime, theme |
| `profiles.py` | Production vs dev profile (`apply_production_profile`) |
| `paths.py` | Пути workspace, sandbox, debug roots |
| `fidelity_policy.py` | Политики fidelity tier |
| `generation_domains.py` | Домены генерации (feature routing) |
| `debug_pipeline.py` | Debug-only pipeline flags |

---

## `schemas/` — контракты данных

| Файл | Назначение |
|------|------------|
| `tree.py` | `CleanDesignTreeNode`, `NodeType`, sizing, style |
| `ir.py` | `ScreenIr`, `WidgetIrNode`, extracted widgets |
| `tokens.py` | Design tokens (colors, typography, spacing) |
| `generation.py` | LLM generation response models |
| `geometry.py` | Geometry slots, layout facts |
| `style.py` | Paint, effects, text style |
| `types.py` | Общие enum / aliases |
| `ir_payloads.py` | Payload shapes для LLM strict JSON |
| `reusable_candidates.py` | Кандидаты reusable widgets из LLM |

---

## `cli/` — точка входа Typer

| Файл | Назначение |
|------|------------|
| `__init__.py` | Регистрация команд `figma-flutter` |
| `generate.py` | Основная генерация экрана |
| `live.py` | `live-check`, smoke с реальным Figma |
| `fixtures.py` | Offline / demo-signoff / corpus |
| `oracle.py` | Corpus oracle CLI |
| `semantics.py` | Semantics corpus gate |
| `fidelity.py` | Fidelity reports |
| `preview.py` | Preview-related CLI |
| `batch.py` | Пакетная генерация |
| `audit.py` | Audit helpers CLI |
| `helpers.py` | Общие опции CLI |

---

## `figma/` — коннектор Figma REST

| Файл / папка | Назначение |
|--------------|------------|
| `client.py` | HTTP client, auth, retry |
| `http.py` | Low-level requests |
| `url.py` | Парсинг Figma URL → file key, node id |
| `nodes.py` | Fetch nodes API |
| `images.py` | Export images/SVG |
| `models.py` | DTO ответов API |
| `limits.py` | Rate limits, batching |
| `endpoints/` | Разбивка REST endpoints (`base`, `nodes`, `metadata`, `images`) |

---

## `parser/` — Figma JSON → clean tree + tokens

### Корень `parser/`

| Файл | Назначение |
|------|------------|
| `tree.py` | **Главный parse:** Figma node → `CleanDesignTreeNode` |
| `tree_node.py` | Построение узлов, children, metadata |
| `geometry.py` | Bounds, transforms, constraint hints |
| `geometry_frames.py` | Frame / artboard geometry |
| `render_bounds.py` | Visible render bounds |
| `components.py` | Component instances, variants |
| `component_raw.py` | Сырой component metadata |
| `styles.py` | Fills, strokes, effects mapping |
| `style_refs.py` | Style references |
| `effects.py` | Blur, shadows |
| `typography.py` | Text styles |
| `text_metrics.py` | Font metrics hints |
| `text_normalize.py` | Нормализация текста |
| `text_line_height.py` | Line height из Figma |
| `text_case.py` | Letter case |
| `richtext.py` | Mixed-style text |
| `css.py` | CSS synthesis (Dev Mode) |
| `dev_mode_css.py` | Dev Mode CSS extraction |
| `accessibility.py` | A11y hints |
| `animations.py` | Figma transitions (metadata) |
| `transitions.py` | Prototype transitions |
| `prototype.py` | Prototype graph hints |
| `navigation.py` | Prototype navigation links |
| `viewport_inset.py` | Safe area / viewport |
| `overlap_sweep.py` | Sweep-line overlap analysis |
| `z_dag.py` | Z-order DAG |
| `z_bands.py` | Z-band grouping |
| `stack_paint.py` | Stack paint order |
| `tree_text.py` | Text descendant helpers |
| `tree_walk.py` | Cycle-safe DFS (`CleanTreeCycleError`) |
| `truth_snapshot.py` | Snapshot фактов для debug/diff |
| `design_coverage.py` | Design coverage report model |
| `ux.py` / `ux_report.py` | UX analysis report |
| `numeric_rounding.py` | Округление координат |
| `version.py` | Parser version stamp (cache invalidation) |

### `parser/dedup/` — кластеры и prune

| Файл | Назначение |
|------|------------|
| `signatures.py` | Structural signature для equivalence class |
| `clusters.py` | `assign_structural_clusters` |
| `instances.py` | Instance ↔ cluster mapping |
| `prune.py` | `prune_duplicated_cluster_subtrees` |
| `hydrate.py` | Hydrate cluster metadata после prune |
| `hints.py` | Dedup hints из имён/структуры |

### `parser/boundaries/` — render boundaries и ассеты

| Файл | Назначение |
|------|------------|
| `assets.py` | **Asset index**, discover keys, vector/image resolve |
| `collapse.py` | Collapse decorative boundaries |
| `heuristics.py` | Boundary heuristics |
| `ids.py` | Boundary id normalization |
| `models.py` | Boundary DTO |

### `parser/tokens/` — design tokens

| Файл | Назначение |
|------|------------|
| `build.py` | Сбор token map из дерева + styles |
| `tree.py` | Token tree walk |
| `colors.py` | Color tokens |
| `variables.py` | Figma variables |
| `import_json.py` | Import external token JSON |
| `naming.py` | Token naming conventions |

### `parser/interaction/` — эвристики интерактива (pre-semantic)

| Файл | Назначение |
|------|------------|
| `forms.py` | Checkbox, form chrome facts |
| `input_fields.py` | Input field detection signals |
| `inline_input_hosts.py` | Inline input hosts |
| `buttons.py` | Button-like structures |
| `chips.py` / `chip_variant.py` | Chips |
| `selection.py` | Selection controls |
| `step.py` | Stepper |
| `icons.py` | Icon interaction |
| `absolute_fields.py` | Absolute-positioned fields |
| `product.py` | Product-card patterns |
| `enrichment.py` | Enrich tree с interaction facts |
| `signals.py` / `shared.py` | Shared signal helpers |
| `text_actions.py` | Tappable text |

### `parser/layout/` — reconcile на parse-стороне

| Файл | Назначение |
|------|------------|
| `reconcile_registry.py` | Реестр reconcile passes + policy |
| `placement.py` | Placement facts |
| `sizing.py` | Sizing reconcile |
| `grid.py` | Grid layouts |
| `reconcilers_align.py` | Alignment reconcile |
| `reconcilers_media.py` | Media / hero reconcile |
| `reconcilers_grid.py` | Grid hydrate |
| `reconcilers_grid_hydrate.py` | Grid hydration details |
| `reconcilers_ui.py` | UI chrome reconcile |

### `parser/semantics/` — классификация (candidate, не emit)

| Файл | Назначение |
|------|------------|
| `classify.py` | Orchestration classification |
| `arbiter.py` | Разрешение конфликтов detectors |
| `prefilter.py` | Pre-filter nodes |
| `models.py` | Verdict models |
| `report.py` | Semantic report output |
| `metrics.py` | Metrics для corpus |
| `corpus.py` | Semantics corpus gate data |

**`detectors/`:** `controls`, `inputs`, `navigation`, `actions`, `display`, `overlays`, `registry`, `_base`

**`signals/`:** `anatomy`, `geometry`, `properties`, `type_trust`, `chip_anatomy`

### `parser/annotations/`

| Файл | Назначение |
|------|------------|
| `widget_marker.py` | Figma layer markers для extraction |

---

## `assets/` — экспорт файлов в Flutter project

| Файл | Назначение |
|------|------------|
| `exporter.py` | Orchestration export |
| `collect.py` | Collect export candidates из дерева |
| `files.py` | Write files to disk |
| `directories.py` | Asset folder layout |
| `names.py` | Asset filename rules |
| `boundaries.py` | Render-boundary exports |
| `composite_icons.py` | Composite icon export |
| `eligibility.py` | What to export |
| `effects.py` | Effect rasterization hooks |
| `optimize.py` / `webp.py` | Optimization |
| `diagnostics.py` / `reporting.py` | Asset gap reports |
| `screen_frame.py` | Screen frame PNG for golden |
| `models.py` | Asset manifest models |

---

## `fonts/` — шрифты в проект

| Модуль | Назначение |
|--------|------------|
| `resolver.py` / `registry.py` | Match Figma font → files |
| `googlefonts.py` / `local.py` | Sources |
| `bundle.py` / `collector.py` | Bundle into project |
| `apply.py` | pubspec + theme hooks |
| `metrics.py` / `diagnostics.py` | Font metrics & gaps |
| `data/font-registry.v1.yaml` | Registry data |

*(Остальные файлы — paths, cache, offers, overrides, naming_hint — поддержка resolver.)*

---

## `llm/` — structured intent (не финальный Dart)

| Файл | Назначение |
|------|------------|
| `schema.py` | JSON schema для strict output |
| `ir_payload.py` | Сбор payload для generate |
| `payload_slim.py` / `payload_format.py` | Slim vs full tree в prompt |
| `semantic_context.py` | Semantic context для LLM |
| `reusable_candidates.py` | Reusable widget proposals |
| `enrich_clusters.py` | Cluster enrichment для LLM |
| `repair.py` / `repair_apply.py` | LLM repair orchestration |
| `unified_diff.py` | Apply unified diff на Dart |
| `refine_context.py` | Visual refine context |
| `reasoning.py` | Reasoning mode toggle |
| `capabilities.py` | Provider capabilities |
| `compare.py` | Compare LLM outputs |
| `repair_models.py` / `refine_models.py` | Pydantic repair/refine models |
| `cpi_supervisor.py` | CPI repair supervision |
| `openrouter_fusion.py` / `openrouter_usage.py` | OpenRouter specifics |
| `line_numbered_source.py` | Numbered source для repair prompt |

**`clients/`:** `factory`, `protocol`, `google`, `openai`, `anthropic`, `openrouter`, `retry`, `response`, `content`

**`prompts/`:** `generation`, `repair`, `principles`, `compose`, `environment`, `visual`, `cpi`, `actions`, `capabilities`, `models`, `shared`

**`repair_scope/`:** scope repair по paths, semantics, locations

---

## `pipeline/` — оркестрация

| Файл | Назначение |
|------|------------|
| `deps.py` | **DI root:** factories для connector, LLM, writer |
| `dump.py` | Load/save offline dumps |
| `dump_prefetch.py` | Prefetch screen dumps |
| `incremental.py` | Incremental run policy |
| `llm.py` | Pipeline-level LLM stage wiring |
| `local_assets.py` | Local asset resolution |
| `reusable_cache.py` | Cache reusable LLM artifacts |
| `warning_policy.py` | Warning → error policy |
| `dry_run.py` | Dry-run mode |
| `result.py` | Pipeline result model |
| `helpers.py` | Shared pipeline helpers |

**`run/`**

| Файл | Назначение |
|------|------------|
| `core.py` | **`run_pipeline`** main loop |
| `stages.py` | Phase: fetch+parse, plan, write |
| `fetch.py` | Fetch phase |
| `commit.py` | Git commit / PR hooks |

---

## `stages/` — стадии pipeline (thin wrappers)

| Файл | Назначение |
|------|------------|
| `fetch.py` | Figma fetch stage |
| `parse.py` | Parse frame stage |
| `llm.py` | LLM generate IR |
| `plan.py` | Plan Dart files |
| `validate.py` | Pre-write validation |
| `write.py` | Write to disk + sync |
| `assets.py` | Asset export stage |
| `fonts.py` | Font stage |
| `snapshot.py` | Debug snapshot dump |
| `runtime_geometry_check.py` | Runtime geometry validation |

**`llm_repair/`:** `loop`, `deterministic`, `syntax`, `replan`, `cpi`, `finalize` — repair loop

**`visual_refine/`:** `loop`, `helpers`, `models` — pixel refine (optional)

---

## `generator/` — ядро codegen

### Корень `generator/`

| Файл | Назначение |
|------|------------|
| `normalize.py` | **Canonicalize clean tree:** IR guards, geometry, assets, reconcile |
| `codegen.py` | Codegen orchestration helpers |
| `renderer.py` | Jinja render entry |
| `renderer_theme.py` / `renderer_bootstrap.py` | Theme + main.dart |
| `widget_extractor.py` | **Cluster widgets:** collect, render, materialize delegates |
| `cluster_variants.py` | Vector variants для clusters |
| `navigation_codegen.py` | Router / nav files |
| `destinations.py` | Multi-destination screens |
| `pubspec.py` / `pub_get_policy.py` | pubspec updates |
| `theme_typography.py` | Typography theme generation |
| `normalize.py` | см. выше |
| `paths.py` | Output paths |
| `artboard.py` | Artboard sizing |
| `chunking.py` | Large tree chunking |
| `tree_copy.py` | Deep copy clean tree |
| `custom_code_zones.py` | Preservation zones |
| `cascade_context.py` | Cascade style context |
| `emit_text_span.dart` | Text span emit helpers |
| `emit_fidelity_audit.py` | Fidelity audit emit |
| `pixel_policy.py` | Pixel policy |
| `render_surface.py` / `render_units.py` | Render units |
| `variant_topology.py` | Variant topology |
| `widget_models.py` / `widget_validation.py` | Widget metadata |
| `reconcile_ast_cache.py` | AST reconcile cache |
| `capture_screen_test.py` | Golden test scaffold |
| `app_typography_collapse.py` | Typography collapse |

### `generator/planner/` — план Dart-файлов

| Файл | Назначение |
|------|------------|
| `plan.py` | **`plan_generation_files`** — subtrees, normalize, layout passes |
| `context.py` | `GenerationPlanContext` |
| `cluster_subtree.py` | Subtree widgets, prune, plan |
| `ir_render.py` | Materialize IR → screen/router |
| `finalize.py` | Theme, bootstrap, tests, final reconcile |
| `screen_reconcile.py` | Screen-level reconcile |
| `fixtures.py` | Planner fixtures |
| `timing.py` | Substage timing logs |

### `generator/ir/` — Screen IR compiler

| Файл | Назначение |
|------|------------|
| `screen.py` | Screen IR models / helpers |
| `tree.py` | `merge_screen_ir`, IR tree walk |
| `materialize.py` | Materialize IR structures |
| `extracted.py` | Extracted widget IR |
| `extracted_paint.py` | Paint из extracted |
| `expression.py` | **Главный emit:** `emit_screen_body_from_ir`, `emit_widget_expression` |
| `semantic_emit.py` | Semantic template routing |
| `fidelity_router.py` | Route fidelity tier → emit strategy |
| `fidelity_manifest.py` | Load manifest YAML |
| `context.py` | `IrEmitContext` |
| `style_context.py` | Style during emit |
| `states.py` | Interactive states |
| `repair.py` | IR-level repair helpers |
| `version.py` | IR schema version |

**`validate/`:** `__init__` (render safety), `graph`, `guards`, `tokens`, `viewport`, `root_kind`

**`passes/`:** `manager`, `registry`, `planner`, `sync`, `geometry`, `semantic`, `fidelity`, `policy`, `contract`, `sectionize`, `scroll_host`, `unstack`, `unpin`, `layout_criteria`, `provenance_*`

**`fidelity/`:** `router`, `stamp`, `promote`, `baked_gate`, `baked_emit`, `styled_emit`, `text_policy`, `report`, `manifest`

**`contracts/`:** `laws.py`, `emit_recipes.py` (recipes registry, report-only)

**`presence/`:** tree presence, kinds, sanitize, semantics, subtrees, stack

**`data/fidelity_manifest.yaml`:** tier definitions

### `generator/layout/` — deterministic Dart layout

| Файл | Назначение |
|------|------------|
| `file.py` / `widget_file.py` | File-level layout emit |
| `file_preamble.dart` | Imports preamble |
| `common.py` | Shared layout utils |
| `responsive.py` / `responsive_grid.py` | Breakpoints |
| `scroll.py` | Scroll hosts |
| `stack_chrome.py` | Bottom nav overlay, terminal chrome |
| `flex_reconcile.py` | Flex reconcile |
| `form.py` | Form layout |
| `interactive.py` / `interactive_chrome.py` | Interactive chrome |
| `segmented_pill.py` | Segmented control |
| `choice_chip_row.py` | Chip rows |
| `button_flow.py` | Button flow layout |
| `geometry_facts.py` | Layout facts |
| `cupertino.py` | Cupertino variants |

**`flex_policy/`:** `row`, `column`, `stack`, `wrap`, `extents`, `alignment`, `facts`, `buttons`, `text` — **ядро flex law**

**`style/`:** `decoration`, `colors`, `text`, `text_emit`, `facts`

**`navigation/`:** `bottom`, `items`, `tabs`, `chrome`, `host`, `labels`, `tree`, `helpers`

**`widgets/`:** `layout.py`, `positioned.py`, `text.py`, `svg.py`, `decoration.py`, `flex_sizing.py`, `hero.py`, `finalize.py`, …

**`widgets/emit/`** — dispatch emit по node kind:

| Файл | Назначение |
|------|------------|
| `dispatch.py` | **Router** emit по type/kind |
| `flex.py` | Row/Column emit |
| `stack.py` | Stack + Positioned |
| `containers.py` | Container/decorations |
| `controls.py` | Controls emit |
| `text.py` | Text emit |
| `media.py` | Image/SVG |
| `shell.py` | Scaffold/shell |
| `tab_switcher.py` | Tabs |
| `helpers.py` / `context.py` | Emit context |

**`widgets/input/`:** `fields`, `decoration`, `currency`, `inline_hosts`, `absolute_fields`

**`widgets/button/`:** `core`, `cta_footer`, `checkbox_rows`

### `generator/geometry/` — geometry planner

| Файл | Назначение |
|------|------------|
| `planner.py` | `plan_geometry_tree` |
| `affine.py` | Affine transforms |
| `slots.py` | Layout slots |
| `flex.py` | Flex geometry |
| `baseline.py` | Baselines |
| `repaint.py` | Repaint boundaries |
| `text_metrics.py` | Text metrics |
| `emit_invariants.py` | Emit-time geometry checks |

**`invariants/`:** `conservation`, `validate`, `checks`, `reporting`, `checkpoints`, `type_truth`, `models`

### `generator/planned/` — planned Dart graph

| Файл | Назначение |
|------|------------|
| `graph.py` | Planned file graph invariants |

**`reconcile/`:** `imports`, `delegate`, `delegate_repair`, `widget_prune`, `hydrate`, `shell`, `ctor_repair`, `syntax_repair`, `bootstrap_refresh`, `class_inspect`, `paths`, `ast_helpers`

### `generator/widget_extraction/` — policy extraction

| Файл | Назначение |
|------|------------|
| `collect.py` | Collect extraction specs |
| `eligibility.py` | Eligibility rules |
| `gates.py` | Policy gates |
| `scorer.py` | Score candidates |
| `shape.py` | Widget shape |
| `policy.py` | Extraction policy |
| `semantic.py` | Semantic extraction |
| `enrich.py` | Enrich specs |
| `naming.py` / `props.py` / `variant_params.py` | Naming & props |

### `generator/dart/` — post-emit Dart

| Файл | Назначение |
|------|------------|
| `syntax_repairs.py` | Syntax repairs |
| `static_contract_gates.py` | Static gates |
| `layout_strip.py` / `layout_extract.py` | Layout extract/strip |
| `delimiters.py` / `delimiter_expression.py` | Dart delimiter safety |
| `file_parts.py` | Split Dart file parts |

**`project_validation/`:** `analyze`, `format`, `write_analyze`, `planned`, `planned_analyze`, `toolchain`

**`postprocess/`:** imports, text, calls, rules

**`llm_codegen/`:** legacy/alternate LLM dart fragments (controls, positioned, widgets)

### `generator/templates/` — Jinja2 Dart templates

| Группа | Файлы |
|--------|--------|
| App shell | `main.dart.j2`, `app_router*.j2`, `app_theme.dart.j2`, `app_colors/spacing/radius/elevation/edge_insets` |
| Screen | `screen.dart.j2`, `destination_screen.dart.j2` |
| State | `state_riverpod/bloc/provider.dart.j2` |
| Widgets | `templates/widgets/*.dart.j2` — button, input, card, chip, nav_scroll_host |
| Tests | `golden_screen_test.dart.j2`, `typography_specimens_test.dart.j2` |
| Prototype | `prototype_navigation.dart.j2`, `prototype_scroll_targets.dart.j2` |

### Прочие подпакеты `generator/`

| Модуль | Назначение |
|--------|------------|
| `subtree/` | Auth buttons, subtree blocks, merge, plan, render |
| `background/` | Ambient background detection/sync/render |
| `figma_anchor/` | Figma id anchors, paint order, coverage |
| `variant/` | Variant config, controls, actions, state |
| `rendering/` | Injection points для screens/tests/navigation |
| `checks/` | Text scaler, layout validate |
| `writing/` | **Writer:** disk I/O, custom_code merge |
| `visual/renderer.py` | Visual preview renderer |

---

## `validation/` — верификация

| Модуль | Назначение |
|--------|------------|
| `compare.py` | Compare renders |
| `iou.py` | IoU metrics |
| `geometry_metrics.py` | Geometry comparison |
| `runtime_geometry.py` | Runtime geometry check |
| `surgical_refine.py` | Surgical pixel patches |
| `golden_runtime.py` | Golden runtime selection |
| `reference.py` / `specimens.py` | Reference specimens |

**`golden_capture/`:** docker/host capture, warm sandbox, paths, logs

**`oracle/`:** corpus oracle runner, evaluator, profile_compare, promotion_evidence

**`pixel/`:** bands, masks, heatmap, perfect_gate, split_compare

**`spec23/`:** production readiness evaluator (§23 spec)

---

## `sync/` — incremental sync

| Файл | Назначение |
|------|------------|
| `regions.py` | `<auto-generated>` / `<custom-code>` regions |
| `snapshot.py` | File hash snapshot |
| `diff.py` | Diff-driven updates |

---

## `debug/` — артефакты `.debug/screen/`

| Файл | Назначение |
|------|------------|
| `paths.py` | Path layout v9 |
| `dumps.py` / `ir_dumps.py` | Write raw/processed/pre_emit JSON |
| `provenance.py` | `provenance.json` |
| `semantics.py` / `fidelity.py` | Semantic/fidelity debug |
| `dart_bundle.py` | Bundle for analyze |
| `emitter_reference.py` | Reference emit for diff |
| `run_meta.py` | `run.meta.json` |
| `ir_cache.py` | IR cache helpers |
| `capture.py` | Capture metadata |
| `responsiveness.py` | Responsiveness report |
| `terminal_log.py` / `agent_logs.py` | Log mirrors |

---

## `fixtures/` — offline corpus

| Файл | Назначение |
|------|------------|
| `screens_manifest.py` | Load `tests/fixtures/screens.yaml` |
| `golden_compare.py` / `golden_baseline.py` | Golden fixtures |
| `bulk_ir_validate.py` | Bulk IR validation |
| `geometry_check.py` | Fixture geometry |
| `capture_context.py` | Capture context for fixtures |

---

## Периферия (свёрнуто, без дерева файлов)

| Модуль | Назначение |
|--------|------------|
| **`dev/`** | Interactive wizard (`dev/wizard/`), OpenCode integration, import Figma, JSON websocket, view render plan |
| **`wizard/`** | Legacy wizard fetch/preflight поверх pipeline |
| **`batch/`** | Batch full-file dumps для нескольких экранов |
| **`audit/`** | Predicate overlap matrix, reviewer docs — не в runtime generate |
| **`observability/`** | `new_run_id()`, stage timing wrappers |
| **`tools/`** | AST sidecar invoke, process run, stale cleanup |
| **`preview/`** | Preview server / render preview |
| **`src/control_panel/`** | FastAPI API, Discord bot, ARQ workers, Postgres jobs, publish PR — отдельный продуктовый слой |

---

## Вне пакета (связано с генерацией)

| Путь | Назначение |
|------|------------|
| `tests/` | Pytest: emit laws, conservation, fixtures, golden |
| `tests/fixtures/screens.yaml` | Offline screen manifest |
| `.debug/screen/<project>/<feature>/` | Per-screen debug bundle |
| `tools/dart_ast_sidecar/` | Dart AST compiler (post-emit) |
| `scripts/signoff.ps1` | CI gate |
| `refactor/` | RAR programs, system prompt, эта карта |

---

## Быстрая навигация по симптому

| Симптом | Смотри первым |
|---------|----------------|
| Wrong Figma fact | `parser/tree.py`, `geometry.py` |
| Wrong IR / children | `generator/ir/`, `normalize.py` |
| Wrong widget kind | `parser/semantics/`, `ir/passes/policy.py` |
| Wrong layout Dart | `generator/layout/widgets/emit/`, `flex_policy/` |
| Missing asset | `parser/boundaries/assets.py`, `stages/assets.py` |
| Empty cluster widget | `widget_extractor.py`, `parser/dedup/` |
| Analyze fail | `generator/dart/project_validation/`, `planned/reconcile/` |
| Hang / slow plan | `planner/plan.py`, `normalize.py`, `planner/timing.py` |
| Golden mismatch | `validation/golden_capture/`, `validation/oracle/` |
