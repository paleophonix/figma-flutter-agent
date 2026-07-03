**

# Figma → Flutter Adaptive Layout Agent

---

# 1. Общая информация

## Название

Figma to Flutter Adaptive Layout Agent

---

# Назначение

Разработать AI-агента, который:

- получает дизайн из Figma;
    
- анализирует структуру макета;
    
- извлекает стили через Figma Dev Mode/API;
    
- генерирует production-ready адаптивную верстку на Flutter.
    

Агент должен:

- понимать структуру UI;
    
- строить reusable widgets;
    
- генерировать responsive layout;
    
- поддерживать design system;
    
- учитывать best practices Flutter.
    

---

# Главная цель

Автоматизировать:

- верстку экранов;
    
- создание UI-компонентов;
    
- адаптацию под разные устройства;
    
- перенос design system из Figma в Flutter.
    

---

# 2. Основные задачи агента

Агент должен:

1. Подключаться к Figma API.
    
2. Читать Dev Mode/CSS styles.
    
3. Анализировать структуру макета.
    
4. Определять reusable components.
    
5. Генерировать Flutter UI.
    
6. Делать responsive/adaptive layout.
    
7. Генерировать theme/design system.
    
8. Экспортировать assets.
    
9. Подготавливать production-ready Flutter code.
    

---

# 3. Поддерживаемые технологии

# Input

## Figma

- Figma API
    
- Dev Mode
    
- CSS extraction
    
- Design tokens
    
- Auto Layout metadata
    

---

# Output

## Flutter

Поддержать:

- Material 3
    
- Cupertino
    
- Flutter Web
    
- Mobile
    
- Tablet
    

---

## State Management

Опционально:

- Riverpod
    
- BLoC
    
- Provider
    

---

# 4. Основные сценарии использования

# Use Cases

## 1. Генерация нового экрана

Из Figma frame → Flutter screen.

---

## 2. Генерация design system

Создание:

- colors;
    
- typography;
    
- spacing;
    
- components.
    

---

## 3. Генерация reusable widgets

Автоматическое выделение:

- buttons;
    
- cards;
    
- inputs;
    
- modals;
    
- lists.
    

---

## 4. Responsive adaptation

Поддержка:

- mobile;
    
- tablet;
    
- desktop;
    
- web.
    

---

## 5. Design update synchronization

Обновление Flutter UI после изменения Figma.

---

# 5. Интеграция с Figma

# 5.1 Figma API

Использовать:

- Figma REST API
    
- Dev Mode API
    
- Nodes API
    
- Styles API
    
- Components API
    

---

# 5.2 Получаемые данные

## Layout

- frame hierarchy
    
- constraints
    
- auto-layout
    
- spacing
    
- alignment
    

---

## Styling

- colors
    
- typography
    
- shadows
    
- radius
    
- opacity
    
- gradients
    

---

## Assets

- SVG
    
- PNG
    
- icons
    
- illustrations
    

---

## Components

- variants
    
- component sets
    
- states
    

---

# 6. Основной Workflow

Figma URL/File ID

       ↓

Fetch Figma nodes

       ↓

Parse design tree

       ↓

Extract styles/tokens

       ↓

Detect reusable widgets

       ↓

Generate responsive layout

       ↓

Generate Flutter components

       ↓

Generate theme system

       ↓

Export assets

       ↓

Build final Flutter screen

---

# 7. Функциональные требования

# 7.1 Design Tree Parser

Агент должен:

- строить дерево UI;
    
- понимать hierarchy;
    
- анализировать nesting.
    

---

## Поддерживаемые элементы

### Containers

- Frame
    
- Group
    
- Section
    

### UI

- Text
    
- Image
    
- Vector
    
- Button
    
- Input
    
- Card
    
- Modal
    

---

# 7.2 Auto Layout Analyzer

Агент должен:

- понимать Figma Auto Layout;
    
- переводить его в Flutter layout system.
    

---

## Mapping

### Figma → Flutter

Horizontal AutoLayout → Row

Vertical AutoLayout → Column

Wrap → Wrap

Constraints → Align/Expanded/Flexible

---

# 7.3 Responsive Layout Engine

Агент должен:

- автоматически адаптировать UI;
    
- поддерживать breakpoints;
    
- генерировать responsive widgets.
    

---

# Поддерживаемые размеры

## Mobile

- 320–480
    
- 481–768
    

## Tablet

- 769–1024
    

## Desktop/Web

- 1025+
    

---

# Responsive Rules

## Agent должен:

- заменять fixed sizes;
    
- использовать flexible layouts;
    
- применять MediaQuery/LayoutBuilder;
    
- избегать overflow.
    

---

# 7.4 Flutter Widget Generator

# Генерируемые widgets

## Base Widgets

- Scaffold
    
- AppBar
    
- SafeArea
    
- Container
    
- Row
    
- Column
    
- Stack
    
- ListView
    
- GridView
    

---

## Form Widgets

- TextField
    
- Dropdown
    
- Checkbox
    
- Radio
    
- Switch
    

---

## Advanced Widgets

- Tabs
    
- BottomNavigation
    
- Sliders
    
- Dialogs
    
- Cards
    
- Carousels
    

---

# 7.5 Component Detection

Агент должен автоматически находить:

- повторяющиеся элементы;
    
- common patterns;
    
- reusable blocks.
    

---

## Пример

### В Figma

10 одинаковых карточек.

### Генерация

ProductCard widget

вместо:

10 duplicated Containers

---

# 7.6 Design System Generator

Агент должен генерировать:

# Theme Files

## Colors

AppColors.primary

---

## Typography

AppTypography.titleLarge

---

## Spacing

AppSpacing.md

---

## Radius

AppRadius.lg

---

# 7.7 Asset Export

Поддержать:

- SVG export;
    
- PNG export;
    
- WebP;
    
- icon optimization.
    

---

# Генерация структуры

/assets

 /icons

 /images

 /illustrations

---

# 7.8 Navigation Generator

Агент должен:

- определять screen navigation;
    
- генерировать routes.
    

---

## Поддержка

- GoRouter
    
- AutoRoute
    
- Navigator 2.0
    

---

# 7.9 Accessibility

Агент должен:

- добавлять semantics;
    
- поддерживать screen readers;
    
- учитывать contrast;
    
- scalable fonts.
    

---

# 8. Архитектура Flutter Output

# Структура проекта

/lib

 /core

 /theme

 /widgets

 /features

 /screens

 /generated

---

# Layering

Поддержать:

- feature-first  
    или
    
- clean architecture.
    

---

# 9. Генерация кода

# Требования к коду

## Код должен быть:

- production-ready;
    
- readable;
    
- modular;
    
- reusable;
    
- null-safe;
    
- lint-clean.
    

---

# Запрещено

## Нельзя генерировать:

- giant widget trees;
    
- deeply nested containers;
    
- duplicated widgets;
    
- fixed-width-only layouts.
    

---

# 10. AI Rules

# Агент должен:

## Prefer

- reusable widgets;
    
- const constructors;
    
- composition;
    
- theme usage.
    

---

## Avoid

- magic numbers;
    
- inline styles;
    
- duplicated code.
    

---

# 11. Конфигурация

# Config File

.ai-figma-flutter.yml

---

## Пример

flutter:

 architecture: feature_first

  

responsive:

 enabled: true

  

state_management:

 type: riverpod

  

routing:

 type: go_router

  

theme:

 generate: true

  

assets:

 svg: true

 optimize: true

  

naming:

 widget_suffix: Widget

  

layout:

 avoid_fixed_sizes: true

---

# 12. Архитектура решения

# Компоненты

## 1. Figma Connector

Подключение к Figma API.

---

## 2. Design Tree Parser

Парсинг UI hierarchy.

---

## 3. Style Extractor

Извлечение:

- colors;
    
- typography;
    
- effects.
    

---

## 4. Component Analyzer

Поиск reusable components.

---

## 5. Responsive Engine

Генерация adaptive layout.

---

## 6. Flutter Generator

Генерация Dart code.

---

## 7. Theme Generator

Создание design system.

---

## 8. Asset Pipeline

Экспорт и оптимизация assets.

---

# 13. Поддержка Design Tokens

Агент должен поддерживать:

- colors;
    
- typography;
    
- spacing;
    
- elevation;
    
- radius;
    
- shadows.
    

---

# 14. Поддержка Component Variants

## Figma Variants → Flutter states

Пример:

Button / Primary / Disabled

↓

PrimaryButton(

 enabled: false

)

---

# 15. Оптимизация Flutter UI

# Агент должен:

## Использовать

- const;
    
- lazy lists;
    
- widget extraction;
    
- repaint boundaries.
    

---

## Избегать

- rebuild storms;
    
- unnecessary stacks;
    
- layout overflow.
    

---

# 16. Инкрементальная синхронизация

Агент должен:

- определять изменения в Figma;
    
- обновлять только измененные widgets;
    
- сохранять кастомный код разработчика.
    

---

# 17. Developer Preservation System

# Очень важное требование

Агент НЕ должен:

- перезаписывать custom logic;
    
- ломать developer changes.
    

---

# Решение

## Generated zones

// <auto-generated>

// </auto-generated>

---

# Custom zones

// <custom-code>

// </custom-code>

---

# 19. Интеграция с IDE

# Поддержать

- VSCode
    
- Android Studio
    
- Cursor
    
- Claude Code workflows
    

---

# 20. CI/CD Integration

Опционально:

- auto-generation on Figma update;
    
- pull request creation;
    
- screenshot testing.
    

---

# 21. Будущие улучшения

# Planned Features

## 1. Pixel Perfect Validation

Сравнение:

- screenshot vs figma.
    

---

## 2. Animation Generation

Генерация:

- transitions;
    
- micro animations;
    
- Lottie integration.
    

---

## 3. Dark Theme Generation

Автогенерация dark mode.

---

## 4. AI UX Improvements

Предложения:

- better spacing;
    
- accessibility fixes;
    
- mobile optimization.
    

---

# 22. MVP Scope

# Обязательно

- Figma API integration
    
- Dev Mode parsing
    
- Flutter widget generation
    
- responsive layout
    
- reusable widgets
    
- theme generation
    
- asset export
    

---

# Необязательно

- animations
    
- screenshot tests
    
- dark mode
    
- AI UX optimization
    
- bidirectional sync
    

---

# 23. Критерии приемки

Система считается готовой, если:

- агент подключается к Figma;
    
- корректно извлекает Dev Mode данные;
    
- генерирует адаптивный Flutter UI;
    
- создает reusable widgets;
    
- генерирует design system;
    
- экспортирует assets;
    
- поддерживает responsive layouts;
    
- код production-ready;
    
- developer changes сохраняются.
    

---

# 24. Fidelity non-goals (compile-time contract)

Продуктовая цель **pixel-perfect** достигается на этапе **parse → canonicalize → emit**, без
измерительных петель в рантайме генерации:

- **Golden capture**, **visual-refine**, **pixel-diff loops** и **deterministic_pixel_refine** не
  являются обязательным гейтом фиделити для `generate` (опциональные dev/CI инструменты).
- **Текст 1:1 с Figma** ограничен движком Flutter: истинная типографическая идентичность для
  TEXT-нод возможна только через **растеризацию** (SVG/Image), ценой accessibility и editability.
  Все остальные FID-пункты (радиусы, opacity группы, градиенты, stroke, transform) — compile-time.

См. также [docs/projects/core-audit/refactor-checklist.md](projects/core-audit/refactor-checklist.md).

---

# 25. Fidelity tiers (declarative → raster)

| Tier | Описание | Когда включается |
| --- | --- | --- |
| **T0** | Declarative Flex / Stack / Theme / tokens | Default deterministic `generate` |
| **T1** | Vector / SVG paths для простых иконок | `VECTOR` и малые asset exports |
| **T2** | Raster / `DecorationImage` / PNG export | Универсальные эвристики + опциональный `visual_refine` |
| **T3** | Unsupported → warning в UX / design coverage report | Слои вне контракта emit |

**Non-goals:** full-screen `CustomPaint`, обязательный pixel-refine loop, Node.js Style Dictionary в Flutter repo, auto-commit из webhooks.

**Future (отдельные эпики):** Logic IR (Figma Variables + Conditional prototyping), `figma-flutter watch` + webhooks → PR artifact. См. [docs/roadmap-p3-epics.md](roadmap-p3-epics.md).

  


**