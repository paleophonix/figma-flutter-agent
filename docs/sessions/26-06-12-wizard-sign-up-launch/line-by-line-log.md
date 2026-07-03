# Построчный лог: `figma-flutter -i` launch `sign_up`

Источник: `terminals/39.txt` **T-23 … T-823**.

Краткая сводка: [wizard-launch-sign-up-log-annotated.md](./wizard-launch-sign-up-log-annotated.md).

**T** — номер строки в `terminals/39.txt`; **L** — номер в этом файле. Лог в колонке обрезан до ~100 символов; полный текст — в терминале. Пустые строки — разделители loguru между событиями.

| T | L | Лог (сокращ.) | Комментарий |
|---:|---:|---|---|
| 23 | 1 | `Run mode: launch — cached dump (live only if dump/assets missing)` | Визард: режим launch, кэш dump. |
| 24 | 2 | `Screen: sign_up` | Выбранный экран/feature. |
| 25 | 3 | `Dump: OK (E:/@dev/demo_app/.debug/raw/sign_up_layout.json)` | Сырой Figma JSON на диске — fetch из API не нужен. |
| 26 | 4 | `main.dart wired: sign_up_and_sign_in (mismatch)` | В main.dart другой screen — возможна перезапись при write. |
| 27 | 5 | `Icons: 272 on disk / 20 in dump (complete)` | Статус экспорта иконок (не блокер). |
| 28 | 6 | `Screen: sign_up` | Выбранный экран/feature. |
| 29 | 7 | `Codegen: LLM screen body (fail-fast, no deterministic fallback) ` | Тело sign_up_screen от LLM; fail-fast без deterministic fallback в plan. |
| 30 | 8 | `Device: chrome` | Целевое устройство flutter run. |
| 31 | 9 | `Launching Flutter on chrome after sync…` | После sync: run_pipeline, затем flutter run. |
| 32 | 10 | `2026-05-31 16:30:15.042 \| INFO     \| figma_flutter_agent.pipeline:run_pipeline:163 - Generation…` | Пайплайн: LLM screen body, llm_fallback_to_deterministic=False. |
| 33 | 11 | `` | Пустая строка в логе. |
| 34 | 12 | `2026-05-31 16:30:15.043 \| INFO     \| figma_flutter_agent.pipeline:run_pipeline:168 - Pipeline r…` | Старт run_pipeline. |
| 35 | 13 | `` | Пустая строка в логе. |
| 36 | 14 | `2026-05-31 16:30:17.608 \| INFO     \| figma_flutter_agent.pipeline:run_pipeline:202 - Dev Mode C…` | Подключён css_dump.json. |
| 37 | 15 | `` | Пустая строка в логе. |
| 38 | 16 | `2026-05-31 16:30:17.609 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage fet…` | Стадия fetch. |
| 39 | 17 | `` | Пустая строка в логе. |
| 40 | 18 | `2026-05-31 16:30:17.610 \| INFO     \| figma_flutter_agent.pipeline:run_pipeline:224 - Loaded cac…` | Чтение sign_up_layout.json. |
| 41 | 19 | `` | Пустая строка в логе. |
| 42 | 20 | `2026-05-31 16:30:17.610 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage fet…` | Fetch завершён. |
| 43 | 21 | `` | Пустая строка в логе. |
| 44 | 22 | `2026-05-31 16:30:17.611 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage par…` | Стадия parse. |
| 45 | 23 | `` | Пустая строка в логе. |
| 46 | 24 | `2026-05-31 16:30:17.611 \| INFO     \| figma_flutter_agent.stages.parse:parse_figma_frame:58 - De…` | CSS override при парсинге. |
| 47 | 25 | `` | Пустая строка в логе. |
| 48 | 26 | `2026-05-31 16:30:17.621 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage par…` | Parse завершён. |
| 49 | 27 | `` | Пустая строка в логе. |
| 50 | 28 | `2026-05-31 16:30:17.652 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage fon…` | Стадия fonts. |
| 51 | 29 | `` | Пустая строка в логе. |
| 52 | 30 | `2026-05-31 16:30:17.693 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage fon…` | Fonts завершены. |
| 53 | 31 | `` | Пустая строка в логе. |
| 54 | 32 | `2026-05-31 16:30:17.693 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage ana…` | Analyze дизайн-дерева (не dart analyze). |
| 55 | 33 | `` | Пустая строка в логе. |
| 56 | 34 | `2026-05-31 16:30:17.694 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage ana…` | Analyze дизайна завершён. |
| 57 | 35 | `` | Пустая строка в логе. |
| 58 | 36 | `2026-05-31 16:30:17.701 \| INFO     \| figma_flutter_agent.debug.dumps:write_processed_dump:62 - …` | Dump processed дерева. |
| 59 | 37 | `` | Пустая строка в логе. |
| 60 | 38 | `2026-05-31 16:30:17.705 \| INFO     \| figma_flutter_agent.parser.ux_report:write_analysis_report…` | Отчёт UX. |
| 61 | 39 | `` | Пустая строка в логе. |
| 62 | 40 | `2026-05-31 16:30:17.706 \| INFO     \| figma_flutter_agent.parser.ux_report:write_analysis_report…` | Манифест анимаций. |
| 63 | 41 | `` | Пустая строка в логе. |
| 64 | 42 | `2026-05-31 16:30:17.707 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage llm…` | Стадия LLM. |
| 65 | 43 | `` | Пустая строка в логе. |
| 66 | 44 | `2026-05-31 16:30:17.707 \| WARNING  \| figma_flutter_agent.llm.capabilities:validate_llm_provider…` | Модель не в whitelist (не фатально). |
| 67 | 45 | `` | Пустая строка в логе. |
| 68 | 46 | `2026-05-31 16:30:17.708 \| WARNING  \| figma_flutter_agent.llm.capabilities:log_structured_output…` | JSON schema non-strict для Google. |
| 69 | 47 | `` | Пустая строка в логе. |
| 70 | 48 | `2026-05-31 16:30:17.717 \| INFO     \| figma_flutter_agent.stages.llm:run_llm_stage:147 - Using L…` | Параметры LLM. |
| 71 | 49 | `` | Пустая строка в логе. |
| 72 | 50 | `2026-05-31 16:30:17.718 \| INFO     \| figma_flutter_agent.stages.llm:run_llm_stage:157 - Attache…` | PNG в промпте. |
| 73 | 51 | `to LLM request (69045 bytes)` | — |
| 74 | 52 | `` | Пустая строка в логе. |
| 75 | 53 | `2026-05-31 16:30:17.718 \| WARNING  \| figma_flutter_agent.llm.capabilities:log_structured_output…` | JSON schema non-strict для Google. |
| 76 | 54 | `` | Пустая строка в логе. |
| 77 | 55 | `2026-05-31 16:31:01.319 \| INFO     \| figma_flutter_agent.generator.ir_presence:normalize_screen…` | — |
| 78 | 56 | `presence normalized: +50 node(s) inserted` | — |
| 79 | 57 | `` | Пустая строка в логе. |
| 80 | 58 | `2026-05-31 16:31:01.320 \| WARNING  \| figma_flutter_agent.generator.ir_presence:normalize_screen…` | — |
| 81 | 59 | `presence inserted 50 nodes (cap 40); LLM IR may be under-abstracted — check subtree extraction an…` | — |
| 82 | 60 | `` | Пустая строка в логе. |
| 83 | 61 | `2026-05-31 16:31:01.323 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage llm…` | LLM завершён (~44 с). |
| 84 | 62 | `` | Пустая строка в логе. |
| 85 | 63 | `2026-05-31 16:31:01.323 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage pla…` | Стадия plan. |
| 86 | 64 | `` | Пустая строка в логе. |
| 87 | 65 | `2026-05-31 16:31:01.332 \| INFO     \| figma_flutter_agent.generator.subtree_widgets:plan_subtree…` | План subtree-виджетов. |
| 88 | 66 | `` | Пустая строка в логе. |
| 89 | 67 | `2026-05-31 16:31:01.333 \| INFO     \| figma_flutter_agent.generator.subtree_widgets:plan_subtree…` | Один виджет к рендеру. |
| 90 | 68 | `` | Пустая строка в логе. |
| 91 | 69 | `2026-05-31 16:31:01.334 \| INFO     \| figma_flutter_agent.generator.subtree_widgets:plan_subtree…` | Рендер subtree. |
| 92 | 70 | `` | Пустая строка в логе. |
| 93 | 71 | `2026-05-31 16:31:01.336 \| INFO     \| figma_flutter_agent.generator.subtree_widgets:plan_subtree…` | Subtree готов. |
| 94 | 72 | `` | Пустая строка в логе. |
| 95 | 73 | `2026-05-31 16:31:01.336 \| INFO     \| figma_flutter_agent.generator.planner:plan_generation_file…` | Убраны декоративные Vector. |
| 96 | 74 | `` | Пустая строка в логе. |
| 97 | 75 | `2026-05-31 16:31:01.346 \| INFO     \| figma_flutter_agent.generator.planner:plan_generation_file…` | Детерминированный sign_up_layout.dart. |
| 98 | 76 | `` | Пустая строка в логе. |
| 99 | 77 | `2026-05-31 16:31:01.468 \| WARNING  \| figma_flutter_agent.generator.llm_dart:_ensure_valid_llm_d…` | LLM screen_code битый (лишняя ). |
| 100 | 78 | `` | Пустая строка в логе. |
| 101 | 79 | `2026-05-31 16:31:01.472 \| INFO     \| figma_flutter_agent.generator.llm_dart:ensure_valid_llm_sc…` | Починка скобок. |
| 102 | 80 | `` | Пустая строка в логе. |
| 103 | 81 | `2026-05-31 16:31:04.177 \| WARNING  \| figma_flutter_agent.generator.ambient_background:fix_ambie…` | Патч ambient отклонён. |
| 104 | 82 | `` | Пустая строка в логе. |
| 105 | 83 | `2026-05-31 16:31:04.190 \| WARNING  \| figma_flutter_agent.generator.llm_dart:apply_safe_screen_c…` | Синхронизация текста отклонена. |
| 106 | 84 | `` | Пустая строка в логе. |
| 107 | 85 | `2026-05-31 16:31:06.499 \| INFO     \| figma_flutter_agent.generator.planner:plan_generation_file…` | Финальная reconcile. |
| 108 | 86 | `` | Пустая строка в логе. |
| 109 | 87 | `2026-05-31 16:31:06.505 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | Старт reconcile (13 файлов). |
| 110 | 88 | `` | Пустая строка в логе. |
| 111 | 89 | `2026-05-31 16:31:06.505 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | Incremental AST. |
| 112 | 90 | `` | Пустая строка в логе. |
| 113 | 91 | `2026-05-31 16:31:06.506 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: cluster_variants. |
| 114 | 92 | `` | Пустая строка в логе. |
| 115 | 93 | `2026-05-31 16:31:06.507 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: consolidate_widgets. |
| 116 | 94 | `` | Пустая строка в логе. |
| 117 | 95 | `2026-05-31 16:31:06.508 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: screen_dedupe. |
| 118 | 96 | `` | Пустая строка в логе. |
| 119 | 97 | `2026-05-31 16:31:06.508 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: strip_inline_widgets. |
| 120 | 98 | `` | Пустая строка в логе. |
| 121 | 99 | `2026-05-31 16:31:06.509 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: dedupe_screen_class. |
| 122 | 100 | `` | Пустая строка в логе. |
| 123 | 101 | `2026-05-31 16:31:06.509 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: balance_delimiters. |
| 124 | 102 | `` | Пустая строка в логе. |
| 125 | 103 | `2026-05-31 16:31:06.511 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: align_widget_stems. |
| 126 | 104 | `` | Пустая строка в логе. |
| 127 | 105 | `2026-05-31 16:31:06.512 \| INFO     \| figma_flutter_agent.generator.planned_dart:_log_reconcile_…` | Фаза: sync_widget_imports. |
| 128 | 106 | `` | Пустая строка в логе. |
| 129 | 107 | `2026-05-31 16:31:06.514 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | AST sidecar на файлы. |
| 130 | 108 | `` | Пустая строка в логе. |
| 131 | 109 | `2026-05-31 16:31:09.710 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | AST: sign_up_screen.dart. |
| 132 | 110 | `` | Пустая строка в логе. |
| 133 | 111 | `2026-05-31 16:31:11.992 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | Sidecar screen 2.3 с. |
| 134 | 112 | `` | Пустая строка в логе. |
| 135 | 113 | `2026-05-31 16:31:12.008 \| WARNING  \| figma_flutter_agent.generator.llm_dart:apply_safe_screen_c…` | Патч flex отклонён. |
| 136 | 114 | `` | Пустая строка в логе. |
| 137 | 115 | `2026-05-31 16:31:19.213 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | Backend subprocess. |
| 138 | 116 | `` | Пустая строка в логе. |
| 139 | 117 | `2026-05-31 16:31:19.214 \| INFO     \| figma_flutter_agent.generator.planned_dart:reconcile_plann…` | Reconcile завершён. |
| 140 | 118 | `` | Пустая строка в логе. |
| 141 | 119 | `2026-05-31 16:31:19.215 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage pla…` | Plan готов. |
| 142 | 120 | `` | Пустая строка в логе. |
| 143 | 121 | `2026-05-31 16:31:28.711 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 144 | 122 | `void main() { \| L4: runApp(const MaterialApp(home: SizedBox.shrink()));; regeneration may overwr…` | — |
| 145 | 123 | `` | Пустая строка в логе. |
| 146 | 124 | `2026-05-31 16:31:28.823 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 147 | 125 | `` | Пустая строка в логе. |
| 148 | 126 | `2026-05-31 16:31:29.558 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 149 | 127 | `` | Пустая строка в логе. |
| 150 | 128 | `2026-05-31 16:31:29.559 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 151 | 129 | `` | Пустая строка в логе. |
| 152 | 130 | `2026-05-31 16:31:31.582 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | FAIL: непарсируемый Dart. |
| 153 | 131 | `` | Пустая строка в логе. |
| 154 | 132 | `2026-05-31 16:31:35.855 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/widgets/group6801_widget.dart — warning, не блокер. |
| 155 | 133 | `` | Пустая строка в логе. |
| 156 | 134 | `2026-05-31 16:31:35.857 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 157 | 135 | `` | Пустая строка в логе. |
| 158 | 136 | `2026-05-31 16:31:35.967 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 159 | 137 | `` | Пустая строка в логе. |
| 160 | 138 | `2026-05-31 16:31:36.003 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 161 | 139 | `` | Пустая строка в логе. |
| 162 | 140 | `2026-05-31 16:31:36.024 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 163 | 141 | `2026-05-31 16:31:36.076 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 164 | 142 | `` | Пустая строка в логе. |
| 165 | 143 | `2026-05-31 16:31:36.101 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 166 | 144 | `` | Пустая строка в логе. |
| 167 | 145 | `2026-05-31 16:31:36.123 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 168 | 146 | `` | Пустая строка в логе. |
| 169 | 147 | `2026-05-31 16:31:36.177 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 170 | 148 | `` | Пустая строка в логе. |
| 171 | 149 | `2026-05-31 16:31:38.744 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/features/sign_up/sign_up_screen.dart — warning, не блокер. |
| 172 | 150 | `` | Пустая строка в логе. |
| 173 | 151 | `2026-05-31 16:31:40.892 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 174 | 152 | `` | Пустая строка в логе. |
| 175 | 153 | `2026-05-31 16:31:40.919 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/golden/sign_up_screen_test.dart — warning, не блокер. |
| 176 | 154 | `them` | — |
| 177 | 155 | `` | Пустая строка в логе. |
| 178 | 156 | `2026-05-31 16:31:40.999 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 179 | 157 | `` | Пустая строка в логе. |
| 180 | 158 | `2026-05-31 16:31:41.733 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 181 | 159 | `` | Пустая строка в логе. |
| 182 | 160 | `2026-05-31 16:31:41.733 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 183 | 161 | `` | Пустая строка в логе. |
| 184 | 162 | `2026-05-31 16:31:43.516 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | FAIL: непарсируемый Dart. |
| 185 | 163 | `` | Пустая строка в логе. |
| 186 | 164 | `2026-05-31 16:31:47.771 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/widgets/group6801_widget.dart — warning, не блокер. |
| 187 | 165 | `` | Пустая строка в логе. |
| 188 | 166 | `2026-05-31 16:31:47.774 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 189 | 167 | `` | Пустая строка в логе. |
| 190 | 168 | `2026-05-31 16:31:47.883 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 191 | 169 | `` | Пустая строка в логе. |
| 192 | 170 | `2026-05-31 16:31:47.918 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 193 | 171 | `` | Пустая строка в логе. |
| 194 | 172 | `2026-05-31 16:31:47.942 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 195 | 173 | `2026-05-31 16:31:47.992 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 196 | 174 | `` | Пустая строка в логе. |
| 197 | 175 | `2026-05-31 16:31:48.018 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 198 | 176 | `` | Пустая строка в логе. |
| 199 | 177 | `2026-05-31 16:31:48.040 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 200 | 178 | `` | Пустая строка в логе. |
| 201 | 179 | `2026-05-31 16:31:48.090 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 202 | 180 | `` | Пустая строка в логе. |
| 203 | 181 | `2026-05-31 16:31:50.649 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/features/sign_up/sign_up_screen.dart — warning, не блокер. |
| 204 | 182 | `` | Пустая строка в логе. |
| 205 | 183 | `2026-05-31 16:31:52.790 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 206 | 184 | `` | Пустая строка в логе. |
| 207 | 185 | `2026-05-31 16:31:52.818 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/golden/sign_up_screen_test.dart — warning, не блокер. |
| 208 | 186 | `them` | — |
| 209 | 187 | `` | Пустая строка в логе. |
| 210 | 188 | `2026-05-31 16:31:52.890 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 211 | 189 | `` | Пустая строка в логе. |
| 212 | 190 | `2026-05-31 16:31:53.622 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 213 | 191 | `` | Пустая строка в логе. |
| 214 | 192 | `2026-05-31 16:31:53.622 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 215 | 193 | `` | Пустая строка в логе. |
| 216 | 194 | `2026-05-31 16:31:55.414 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | FAIL: непарсируемый Dart. |
| 217 | 195 | `` | Пустая строка в логе. |
| 218 | 196 | `2026-05-31 16:31:59.664 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/widgets/group6801_widget.dart — warning, не блокер. |
| 219 | 197 | `` | Пустая строка в логе. |
| 220 | 198 | `2026-05-31 16:31:59.667 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 221 | 199 | `` | Пустая строка в логе. |
| 222 | 200 | `2026-05-31 16:31:59.778 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 223 | 201 | `` | Пустая строка в логе. |
| 224 | 202 | `2026-05-31 16:31:59.813 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 225 | 203 | `` | Пустая строка в логе. |
| 226 | 204 | `2026-05-31 16:31:59.836 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 227 | 205 | `2026-05-31 16:31:59.888 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 228 | 206 | `` | Пустая строка в логе. |
| 229 | 207 | `2026-05-31 16:31:59.912 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 230 | 208 | `` | Пустая строка в логе. |
| 231 | 209 | `2026-05-31 16:31:59.936 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 232 | 210 | `` | Пустая строка в логе. |
| 233 | 211 | `2026-05-31 16:31:59.989 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 234 | 212 | `` | Пустая строка в логе. |
| 235 | 213 | `2026-05-31 16:32:02.571 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/features/sign_up/sign_up_screen.dart — warning, не блокер. |
| 236 | 214 | `` | Пустая строка в логе. |
| 237 | 215 | `2026-05-31 16:32:04.720 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 238 | 216 | `` | Пустая строка в логе. |
| 239 | 217 | `2026-05-31 16:32:04.748 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/golden/sign_up_screen_test.dart — warning, не блокер. |
| 240 | 218 | `them` | — |
| 241 | 219 | `` | Пустая строка в логе. |
| 242 | 220 | `2026-05-31 16:32:04.820 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 243 | 221 | `` | Пустая строка в логе. |
| 244 | 222 | `2026-05-31 16:32:05.559 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 245 | 223 | `` | Пустая строка в логе. |
| 246 | 224 | `2026-05-31 16:32:05.560 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 247 | 225 | `` | Пустая строка в логе. |
| 248 | 226 | `2026-05-31 16:32:07.399 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | FAIL: непарсируемый Dart. |
| 249 | 227 | `` | Пустая строка в логе. |
| 250 | 228 | `2026-05-31 16:32:11.736 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/widgets/group6801_widget.dart — warning, не блокер. |
| 251 | 229 | `` | Пустая строка в логе. |
| 252 | 230 | `2026-05-31 16:32:11.738 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 253 | 231 | `` | Пустая строка в логе. |
| 254 | 232 | `2026-05-31 16:32:11.842 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 255 | 233 | `` | Пустая строка в логе. |
| 256 | 234 | `2026-05-31 16:32:11.879 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 257 | 235 | `` | Пустая строка в логе. |
| 258 | 236 | `2026-05-31 16:32:11.901 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 259 | 237 | `2026-05-31 16:32:11.953 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 260 | 238 | `` | Пустая строка в логе. |
| 261 | 239 | `2026-05-31 16:32:11.978 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 262 | 240 | `` | Пустая строка в логе. |
| 263 | 241 | `2026-05-31 16:32:12.002 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 264 | 242 | `` | Пустая строка в логе. |
| 265 | 243 | `2026-05-31 16:32:12.056 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 266 | 244 | `` | Пустая строка в логе. |
| 267 | 245 | `2026-05-31 16:32:14.612 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/features/sign_up/sign_up_screen.dart — warning, не блокер. |
| 268 | 246 | `` | Пустая строка в логе. |
| 269 | 247 | `2026-05-31 16:32:16.760 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 270 | 248 | `` | Пустая строка в логе. |
| 271 | 249 | `2026-05-31 16:32:16.789 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/golden/sign_up_screen_test.dart — warning, не блокер. |
| 272 | 250 | `them` | Продолжение переноса строки лога (хвост WARNING про sign_up_screen_test.dart). |
| 273 | 251 | `` | Пустая строка в логе. |
| 274 | 252 | `2026-05-31 16:32:16.861 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 275 | 253 | `` | Пустая строка в логе. |
| 276 | 254 | `2026-05-31 16:32:17.594 \| WARNING  \| figma_flutter_agent.generator.planned_dart:fallback_unpars…` | FALLBACK: SignUpLayout + shell stub. |
| 277 | 255 | `` | Пустая строка в логе. |
| 278 | 256 | `2026-05-31 16:32:17.595 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/widgets/group6801_widget.dart — warning, не блокер. |
| 279 | 257 | `` | Пустая строка в логе. |
| 280 | 258 | `2026-05-31 16:32:17.598 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 281 | 259 | `` | Пустая строка в логе. |
| 282 | 260 | `2026-05-31 16:32:17.706 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 283 | 261 | `` | Пустая строка в логе. |
| 284 | 262 | `2026-05-31 16:32:17.743 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 285 | 263 | `` | Пустая строка в логе. |
| 286 | 264 | `2026-05-31 16:32:17.765 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 287 | 265 | `'package:flutter/material.dart'; \| L7: class AppTypography { \| L8: AppTypography._();; regenera…` | — |
| 288 | 266 | `` | Пустая строка в логе. |
| 289 | 267 | `2026-05-31 16:32:17.814 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 290 | 268 | `` | Пустая строка в логе. |
| 291 | 269 | `2026-05-31 16:32:17.838 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 292 | 270 | `` | Пустая строка в логе. |
| 293 | 271 | `2026-05-31 16:32:17.860 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 294 | 272 | `` | Пустая строка в логе. |
| 295 | 273 | `2026-05-31 16:32:17.912 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 296 | 274 | `` | Пустая строка в логе. |
| 297 | 275 | `2026-05-31 16:32:20.455 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/features/sign_up/sign_up_screen.dart — warning, не блокер. |
| 298 | 276 | `` | Пустая строка в логе. |
| 299 | 277 | `2026-05-31 16:32:20.541 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 300 | 278 | `` | Пустая строка в логе. |
| 301 | 279 | `2026-05-31 16:32:20.570 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/golden/sign_up_screen_test.dart — warning, не блокер. |
| 302 | 280 | `overwrite them` | — |
| 303 | 281 | `` | Пустая строка в логе. |
| 304 | 282 | `2026-05-31 16:32:20.643 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 305 | 283 | `L3: import 'package:flutter/material.dart'; \| L4: import 'package:flutter/rendering.dart'; \| L5…` | — |
| 306 | 284 | `` | Пустая строка в логе. |
| 307 | 285 | `2026-05-31 16:32:21.382 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 308 | 286 | `` | Пустая строка в логе. |
| 309 | 287 | `2026-05-31 16:32:21.382 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 310 | 288 | `` | Пустая строка в логе. |
| 311 | 289 | `2026-05-31 16:32:23.227 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 312 | 290 | `` | Пустая строка в логе. |
| 313 | 291 | `2026-05-31 16:32:23.228 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Все файлы OK. |
| 314 | 292 | `` | Пустая строка в логе. |
| 315 | 293 | `2026-05-31 16:32:23.235 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage val…` | validate_generated_dart. |
| 316 | 294 | `` | Пустая строка в логе. |
| 317 | 295 | `2026-05-31 16:32:23.238 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage val…` | Validate OK. |
| 318 | 296 | `` | Пустая строка в логе. |
| 319 | 297 | `2026-05-31 16:32:23.239 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage llm…` | llm_repair / spec23. |
| 320 | 298 | `` | Пустая строка в логе. |
| 321 | 299 | `2026-05-31 16:32:23.247 \| WARNING  \| figma_flutter_agent.llm.capabilities:validate_llm_provider…` | Модель не в whitelist (не фатально). |
| 322 | 300 | `` | Пустая строка в логе. |
| 323 | 301 | `2026-05-31 16:32:23.248 \| WARNING  \| figma_flutter_agent.llm.capabilities:log_structured_output…` | JSON schema non-strict для Google. |
| 324 | 302 | `` | Пустая строка в логе. |
| 325 | 303 | `2026-05-31 16:32:23.257 \| INFO     \| figma_flutter_agent.stages.llm_repair:run_analyze_repair_l…` | Модель repair. |
| 326 | 304 | `` | Пустая строка в логе. |
| 327 | 305 | `2026-05-31 16:32:26.368 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 328 | 306 | `void main() { \| L4: runApp(const MaterialApp(home: SizedBox.shrink()));; regeneration may overwr…` | — |
| 329 | 307 | `` | Пустая строка в логе. |
| 330 | 308 | `2026-05-31 16:32:26.472 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 331 | 309 | `` | Пустая строка в логе. |
| 332 | 310 | `2026-05-31 16:32:27.201 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 333 | 311 | `` | Пустая строка в логе. |
| 334 | 312 | `2026-05-31 16:32:28.785 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 335 | 313 | `` | Пустая строка в логе. |
| 336 | 314 | `2026-05-31 16:32:28.804 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | pub get. |
| 337 | 315 | `` | Пустая строка в логе. |
| 338 | 316 | `2026-05-31 16:32:31.757 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | pub get OK. |
| 339 | 317 | `` | Пустая строка в логе. |
| 340 | 318 | `2026-05-31 16:32:31.758 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 341 | 319 | `` | Пустая строка в логе. |
| 342 | 320 | `2026-05-31 16:32:34.702 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | analyze OK. |
| 343 | 321 | `` | Пустая строка в логе. |
| 344 | 322 | `2026-05-31 16:32:34.705 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 345 | 323 | `` | Пустая строка в логе. |
| 346 | 324 | `2026-05-31 16:32:34.705 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 347 | 325 | `` | Пустая строка в логе. |
| 348 | 326 | `2026-05-31 16:32:36.472 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 349 | 327 | `` | Пустая строка в логе. |
| 350 | 328 | `2026-05-31 16:32:36.472 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Все файлы OK. |
| 351 | 329 | `` | Пустая строка в логе. |
| 352 | 330 | `2026-05-31 16:32:36.473 \| INFO     \| figma_flutter_agent.generator.pub_get_policy:log_pub_get_s…` | — |
| 353 | 331 | `get for C:/Users/Home/AppData/Local/Temp/figma-flutter-spec23-j97esmkj/analyze_check (pubspec.yam…` | — |
| 354 | 332 | `` | Пустая строка в логе. |
| 355 | 333 | `2026-05-31 16:32:36.474 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 356 | 334 | `` | Пустая строка в логе. |
| 357 | 335 | `2026-05-31 16:32:39.178 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 358 | 336 | `` | Пустая строка в логе. |
| 359 | 337 | `2026-05-31 16:32:39.179 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 360 | 338 | `` | Пустая строка в логе. |
| 361 | 339 | `2026-05-31 16:32:42.274 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 362 | 340 | `` | Пустая строка в логе. |
| 363 | 341 | `2026-05-31 16:32:42.275 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 364 | 342 | `` | Пустая строка в логе. |
| 365 | 343 | `2026-05-31 16:32:44.951 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 366 | 344 | `` | Пустая строка в логе. |
| 367 | 345 | `2026-05-31 16:32:44.964 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage llm…` | llm_repair OK. |
| 368 | 346 | `` | Пустая строка в логе. |
| 369 | 347 | `2026-05-31 16:32:44.964 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage llm…` | visual_refine. |
| 370 | 348 | `2026-05-31 16:32:44.965 \| INFO     \| figma_flutter_agent.stages.visual_refine:run_visual_refine…` | refine выключен. |
| 371 | 349 | `` | Пустая строка в логе. |
| 372 | 350 | `2026-05-31 16:32:44.965 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage llm…` | refine done. |
| 373 | 351 | `` | Пустая строка в логе. |
| 374 | 352 | `2026-05-31 16:32:44.974 \| INFO     \| figma_flutter_agent.debug.dart_bundle:write_dart_debug_bun…` | — |
| 375 | 353 | `Dart bundle to E:/@dev/demo_app/.debug/dart/sign_up_screen.dart` | — |
| 376 | 354 | `` | Пустая строка в логе. |
| 377 | 355 | `2026-05-31 16:32:48.151 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 378 | 356 | `void main() { \| L4: runApp(const MaterialApp(home: SizedBox.shrink()));; regeneration may overwr…` | — |
| 379 | 357 | `` | Пустая строка в логе. |
| 380 | 358 | `2026-05-31 16:32:48.255 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 381 | 359 | `` | Пустая строка в логе. |
| 382 | 360 | `2026-05-31 16:32:49.009 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 383 | 361 | `` | Пустая строка в логе. |
| 384 | 362 | `2026-05-31 16:32:49.009 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 385 | 363 | `` | Пустая строка в логе. |
| 386 | 364 | `2026-05-31 16:32:50.859 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 387 | 365 | `` | Пустая строка в логе. |
| 388 | 366 | `2026-05-31 16:32:50.859 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Все файлы OK. |
| 389 | 367 | `` | Пустая строка в логе. |
| 390 | 368 | `2026-05-31 16:32:50.867 \| INFO     \| figma_flutter_agent.observability:log_stage:31 - Stage wri…` | Write в demo_app. |
| 391 | 369 | `` | Пустая строка в логе. |
| 392 | 370 | `2026-05-31 16:32:54.025 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 393 | 371 | `void main() { \| L4: runApp(const MaterialApp(home: SizedBox.shrink()));; regeneration may overwr…` | — |
| 394 | 372 | `` | Пустая строка в логе. |
| 395 | 373 | `2026-05-31 16:32:54.129 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 396 | 374 | `` | Пустая строка в логе. |
| 397 | 375 | `2026-05-31 16:32:54.887 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 398 | 376 | `` | Пустая строка в логе. |
| 399 | 377 | `2026-05-31 16:32:54.888 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 400 | 378 | `` | Пустая строка в логе. |
| 401 | 379 | `2026-05-31 16:32:57.233 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 402 | 380 | `` | Пустая строка в логе. |
| 403 | 381 | `2026-05-31 16:32:57.233 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Все файлы OK. |
| 404 | 382 | `` | Пустая строка в логе. |
| 405 | 383 | `2026-05-31 16:32:57.246 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_layout.dart — warning, не блокер. |
| 406 | 384 | `` | Пустая строка в логе. |
| 407 | 385 | `2026-05-31 16:32:57.360 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_colors.dart — warning, не блокер. |
| 408 | 386 | `` | Пустая строка в логе. |
| 409 | 387 | `2026-05-31 16:32:57.395 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_spacing.dart — warning, не блокер. |
| 410 | 388 | `` | Пустая строка в логе. |
| 411 | 389 | `2026-05-31 16:32:57.419 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_typography.dart — warning, не блокер. |
| 412 | 390 | `2026-05-31 16:32:57.471 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_radius.dart — warning, не блокер. |
| 413 | 391 | `` | Пустая строка в логе. |
| 414 | 392 | `2026-05-31 16:32:57.500 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_elevation.dart — warning, не блокер. |
| 415 | 393 | `` | Пустая строка в логе. |
| 416 | 394 | `2026-05-31 16:32:57.524 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/theme/app_theme.dart — warning, не блокер. |
| 417 | 395 | `` | Пустая строка в логе. |
| 418 | 396 | `2026-05-31 16:32:57.580 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits lib/generated/sign_up_layout.dart — warning, не блокер. |
| 419 | 397 | `` | Пустая строка в логе. |
| 420 | 398 | `2026-05-31 16:33:00.288 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits после fallback stub — warning. |
| 421 | 399 | `` | Пустая строка в логе. |
| 422 | 400 | `2026-05-31 16:33:00.388 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits main — warning. |
| 423 | 401 | `` | Пустая строка в логе. |
| 424 | 402 | `2026-05-31 16:33:00.496 \| WARNING  \| figma_flutter_agent.generator.writer:_guard_orphan_edits:3…` | orphan_edits test/harness/element_coordinate_mapper.dart — warning, не блокер. |
| 425 | 403 | `L3: import 'package:flutter/material.dart'; \| L4: import 'package:flutter/rendering.dart'; \| L5…` | — |
| 426 | 404 | `` | Пустая строка в логе. |
| 427 | 405 | `2026-05-31 16:33:01.363 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Batch dart format. |
| 428 | 406 | `` | Пустая строка в логе. |
| 429 | 407 | `2026-05-31 16:33:01.364 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | Subprocess dart format. |
| 430 | 408 | `` | Пустая строка в логе. |
| 431 | 409 | `2026-05-31 16:33:04.424 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | OK: format прошёл. |
| 432 | 410 | `` | Пустая строка в логе. |
| 433 | 411 | `2026-05-31 16:33:04.424 \| INFO     \| figma_flutter_agent.generator.validation:_run_dart_format_…` | Все файлы OK. |
| 434 | 412 | `` | Пустая строка в логе. |
| 435 | 413 | `2026-05-31 16:33:04.447 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | pub get. |
| 436 | 414 | `` | Пустая строка в логе. |
| 437 | 415 | `2026-05-31 16:33:07.601 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | pub get OK. |
| 438 | 416 | `` | Пустая строка в логе. |
| 439 | 417 | `2026-05-31 16:33:07.603 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 440 | 418 | `` | Пустая строка в логе. |
| 441 | 419 | `2026-05-31 16:33:10.336 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 442 | 420 | `` | Пустая строка в логе. |
| 443 | 421 | `2026-05-31 16:33:10.337 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 444 | 422 | `` | Пустая строка в логе. |
| 445 | 423 | `2026-05-31 16:33:13.101 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 446 | 424 | `` | Пустая строка в логе. |
| 447 | 425 | `2026-05-31 16:33:13.101 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:62 - …` | dart analyze (spec23). |
| 448 | 426 | `` | Пустая строка в логе. |
| 449 | 427 | `2026-05-31 16:33:15.671 \| INFO     \| figma_flutter_agent.tools.process_run:run_subprocess:82 - …` | — |
| 450 | 428 | `` | Пустая строка в логе. |
| 451 | 429 | `2026-05-31 16:33:15.671 \| INFO     \| figma_flutter_agent.generator.validation:validate_dart_pro…` | analyze demo_app OK. |
| 452 | 430 | `` | Пустая строка в логе. |
| 453 | 431 | `2026-05-31 16:33:15.675 \| INFO     \| figma_flutter_agent.stages.write:commit_planned_files:170 …` | 13 файлов записано. |
| 454 | 432 | `` | Пустая строка в логе. |
| 455 | 433 | `2026-05-31 16:33:15.676 \| INFO     \| figma_flutter_agent.observability:log_stage:36 - Stage wri…` | Write done. |
| 456 | 434 | `` | Пустая строка в логе. |
| 457 | 435 | `2026-05-31 16:33:15.729 \| WARNING  \| figma_flutter_agent.dev.wizard:generate_screen_for_preview…` | warning FILL. |
| 458 | 436 | `` | Пустая строка в логе. |
| 459 | 437 | `2026-05-31 16:33:15.730 \| WARNING  \| figma_flutter_agent.dev.wizard:generate_screen_for_preview…` | warning nav links. |
| 460 | 438 | `` | Пустая строка в логе. |
| 461 | 439 | `2026-05-31 16:33:15.730 \| WARNING  \| figma_flutter_agent.dev.wizard:generate_screen_for_preview…` | итог: layout delegate, не LLM UI. |
| 462 | 440 | `` | Пустая строка в логе. |
| 463 | 441 | `2026-05-31 16:33:15.731 \| INFO     \| figma_flutter_agent.dev.wizard:generate_screen_for_preview…` | успех визарда. |
| 464 | 442 | `` | Пустая строка в логе. |
| 465 | 443 | `2026-05-31 16:33:15.732 \| INFO     \| figma_flutter_agent.dev.run:launch_flutter_app:165 - Runni…` | pub get перед run. |
| 466 | 444 | `E:/@dev/demo_app` | — |
| 467 | 445 | `` | Пустая строка в логе. |
| 468 | 446 | `Resolving dependencies... ` | вывод pub get. |
| 469 | 447 | `Downloading packages... ` | вывод pub get. |
| 470 | 448 | `  matcher 0.12.19 (0.12.20 available)` | — |
| 471 | 449 | `  meta 1.18.0 (1.18.2 available)` | — |
| 472 | 450 | `  test_api 0.7.11 (0.7.12 available)` | — |
| 473 | 451 | `  vector_graphics_compiler 1.2.3 (1.2.5 available)` | — |
| 474 | 452 | `  vector_math 2.2.0 (2.3.0 available)` | — |
| 475 | 453 | `  xml 6.6.1 (7.0.1 available)` | — |
| 476 | 454 | `Got dependencies!` | pub get OK. |
| 477 | 455 | `6 packages have newer versions incompatible with dependency constraints.` | — |
| 478 | 456 | `Try `flutter pub outdated` for more information.` | — |
| 479 | 457 | `2026-05-31 16:33:18.869 \| INFO     \| figma_flutter_agent.dev.run:launch_flutter_app:175 - Launc…` | flutter run. |
| 480 | 458 | `` | Пустая строка в логе. |
| 481 | 459 | `Launching lib\main.dart on Chrome in debug mode...` | web build. |
| 482 | 460 | `Waiting for connection from debug service on Chrome...             22,8s` | ожидание Chrome. |
| 483 | 461 | `` | Пустая строка в логе. |
| 484 | 462 | `Flutter run key commands.` | справка hot keys. |
| 485 | 463 | `r Hot reload.` | hot reload/restart. |
| 486 | 464 | `R Hot restart.` | hot reload/restart. |
| 487 | 465 | `h List all available interactive commands.` | команда flutter run. |
| 488 | 466 | `d Detach (terminate "flutter run" but leave application running).` | команда flutter run. |
| 489 | 467 | `c Clear the screen` | команда flutter run. |
| 490 | 468 | `q Quit (terminate the application on the device).` | команда flutter run. |
| 491 | 469 | `` | Пустая строка в логе. |
| 492 | 470 | `This app is linked to the debug service: ws://127.0.0.1:55993/18qfArcp2AM=/ws` | debug WS. |
| 493 | 471 | `Debug service listening on ws://127.0.0.1:55993/18qfArcp2AM=/ws` | debug WS. |
| 494 | 472 | `A Dart VM Service on Chrome is available at: http://127.0.0.1:55993/18qfArcp2AM=` | VM URL. |
| 495 | 473 | `The Flutter DevTools debugger and profiler on Chrome is available at:` | DevTools URL. |
| 496 | 474 | `http://127.0.0.1:55993/18qfArcp2AM=/devtools/?uri=ws://127.0.0.1:55993/18qfArcp2AM=/ws` | — |
| 497 | 475 | `Starting ` | Flutter framework (обрезано). |
