# Руководство frontend разработчика

Практическое руководство по разработке в этом проекте.
Архитектурные решения (SDK, стейт, роутинг, API) описаны в [step0_implementation.md](../roadmap/step0_implementation.md).

---

## Содержание

1. [Запуск и окружение](#1-запуск-и-окружение)
2. [Структура проекта](#2-структура-проекта)
3. [Соглашения по коду](#3-соглашения-по-коду)
4. [Добавление нового экрана](#4-добавление-нового-экрана)
5. [Паттерны компонентов](#5-паттерны-компонентов)
6. [Стилизация](#6-стилизация)
7. [Обработка ошибок](#7-обработка-ошибок)
8. [Типы и DTO](#8-типы-и-dto)
9. [Работа с Telegram SDK](#9-работа-с-telegram-sdk)

---

## 1. Запуск и окружение

### Установка

```bash
npm install
```

### Переменные окружения

Создать `.env.local` (не коммитить):

```
VITE_API_URL=https://localhost:8000
VITE_APP_ENV=development
VITE_BOT_URL=https://t.me/your_bot_username
```

`VITE_BOT_URL` используется в экране "Откройте в Telegram" для deeplink-кнопки.

### Локальный запуск

```bash
npm run dev
```

Приложение доступно по **HTTPS** (требование Telegram Mini App).
При первом запуске браузер покажет предупреждение о самоподписанном сертификате — нажать "Продолжить".

### Тестирование в Telegram

1. В [@BotFather](https://t.me/BotFather) прописать URL мини-апп: `https://localhost:5173`
2. Открыть бота в Telegram → нажать кнопку запуска мини-апп
3. Telegram передаст `initData` — авторизация пройдёт через реальный backend

> Для тестирования без Telegram используйте мок `initData`. Подробнее: [документация @tma.js/sdk](https://docs.telegram-mini-apps.com/).

---

## 2. Структура проекта

```
src/
├── api/
│   ├── client.ts           # базовый fetch-wrapper (токен, 401 интерцептор)
│   ├── auth.ts             # /auth/telegram, /auth/me, /auth/me/workspaces
│   └── workspaces.ts       # CRUD workspace, members
├── components/
│   ├── ui/                 # переиспользуемые примитивы
│   │   ├── Button.svelte
│   │   ├── Badge.svelte
│   │   ├── Card.svelte
│   │   ├── Modal.svelte
│   │   ├── Skeleton.svelte
│   │   ├── Toast.svelte
│   │   ├── ProgressBar.svelte
│   │   └── ErrorScreen.svelte
│   └── [feature]/          # компоненты, специфичные для фичи
│       └── WorkspaceCard.svelte
├── routes/
│   ├── +layout.svelte      # корневой layout (QueryClientProvider, init)
│   ├── auth/
│   ├── workspace-select/
│   ├── workspace/[slug]/
│   └── admin/
├── stores/
│   ├── auth.ts             # пользователь + токен
│   └── workspace.ts        # активный workspace + роль
├── lib/
│   ├── types.ts            # общие TypeScript типы и интерфейсы
│   ├── utils.ts            # вспомогательные функции (транслитерация, форматирование)
│   └── guards.ts           # функции проверки ролей
└── app.svelte              # точка входа
```

### Правила именования

| Что | Конвенция | Пример |
|-----|-----------|--------|
| Svelte-компоненты | PascalCase | `WorkspaceCard.svelte` |
| Файлы TypeScript | camelCase | `auth.ts`, `queryKeys.ts` |
| Папки | kebab-case | `workspace-select/` |
| Экспортируемые функции | camelCase | `createWorkspacesQuery` |
| Store-переменные | camelCase | `authStore`, `workspaceStore` |
| Типы / интерфейсы | PascalCase | `WorkspaceState`, `CreateWorkspaceDto` |

---

## 3. Соглашения по коду

### TypeScript

- Строгий режим включён (`strict: true` в `tsconfig.json`)
- Не использовать `any` — если тип неизвестен, использовать `unknown` и сузить через guard
- Типы API-ответов описываются в `src/lib/types.ts`, не инлайн
- DTO для запросов называть с суффиксом `Dto`: `CreateWorkspaceDto`, `PatchWorkspaceDto`

### Svelte

- Реактивные переменные через `$state` (Svelte 5) или `writable` (Svelte 4) — использовать тот подход, который уже применён в проекте
- Избегать бизнес-логики в `.svelte` файлах: выносить в `src/lib/` или composables
- Один компонент — один файл; не создавать «god components»

### Импорты

Использовать алиас `@/` вместо относительных путей:

```ts
// правильно
import { apiClient } from '@/api/client'
import type { Workspace } from '@/lib/types'

// не надо
import { apiClient } from '../../../api/client'
```

---

## 4. Добавление нового экрана

Пошаговый пример: добавить экран «Список мероприятий» (`/workspace/:slug/events`).

### Шаг 1: Создать компонент экрана

Создать файл `src/routes/workspace/[slug]/events/+page.svelte`:

```svelte
<script lang="ts">
  import { createEventsQuery } from '@/api/events'
  import EventCard from '@/components/event/EventCard.svelte'
  import Skeleton from '@/components/ui/Skeleton.svelte'
  import ErrorScreen from '@/components/ui/ErrorScreen.svelte'
  import EmptyState from '@/components/ui/EmptyState.svelte'

  const query = createEventsQuery()
</script>

{#if $query.isLoading}
  <Skeleton count={3} />
{:else if $query.isError}
  <ErrorScreen
    icon="alert-circle"
    title="Ошибка загрузки"
    description="Не удалось загрузить мероприятия"
    actions={[{ label: 'Повторить', variant: 'primary', onClick: () => $query.refetch() }]}
  />
{:else if $query.data?.length === 0}
  <EmptyState text="Мероприятий пока нет" />
{:else}
  {#each $query.data as event}
    <EventCard {event} />
  {/each}
{/if}
```

### Шаг 2: Добавить API-функцию

В `src/api/events.ts`:

```ts
import { createQuery } from '@tanstack/svelte-query'
import { apiClient } from './client'
import type { Event } from '@/lib/types'

export function createEventsQuery(workspaceId: string) {
  return createQuery<Event[]>({
    queryKey: ['workspaces', workspaceId, 'events'],
    queryFn: () => apiClient.get(`/workspaces/${workspaceId}/events`),
  })
}
```

### Шаг 3: Добавить guard (если нужна защита по роли)

Если экран доступен только `workspace_admin` и `assistant`:

```svelte
<!-- в +page.svelte -->
<script lang="ts">
  import { requireRole } from '@/lib/guards'
  requireRole(['workspace_admin', 'assistant']) // редиректит при нарушении
</script>
```

### Шаг 4: Добавить ссылку в NavBar

В `src/components/ui/NavBar.svelte` добавить пункт меню с иконкой и меткой.

### Шаг 5: Добавить тип в `src/lib/types.ts`

```ts
export interface Event {
  id: string
  title: string
  date: string
  price: number | null
  currency: string
}
```

---

## 5. Паттерны компонентов

### Обязательные состояния

Каждый экран со списком или запросом к API должен обрабатывать три состояния:

| Состояние | Компонент |
|-----------|-----------|
| Загрузка | `<Skeleton />` (имитирует форму будущего контента) |
| Ошибка | `<ErrorScreen />` с кнопкой "Повторить" |
| Пустой список | `<EmptyState text="..." />` |

### Скелетон

```svelte
<!-- для списка карточек -->
<Skeleton count={3} variant="card" />

<!-- для одной строки текста -->
<Skeleton variant="text" width="60%" />
```

### Кнопки с loading-состоянием

```svelte
<script lang="ts">
  const mutation = createWorkspaceMutation()
</script>

<Button
  loading={$mutation.isPending}
  disabled={$mutation.isPending || !isFormValid}
  on:click={handleSubmit}
>
  Создать
</Button>
```

### Toast-уведомления

Показывать через store после успешных мутаций:

```ts
import { showToast } from '@/stores/toast'

// после успешного создания
showToast('Пространство создано', 'success')

// при inline-ошибке — не использовать toast, показывать под полем
```

### Модальные окна

```svelte
<script lang="ts">
  let isOpen = false
</script>

<Modal bind:open={isOpen} title="Подтверждение">
  <p>Вы уверены?</p>
  <svelte:fragment slot="actions">
    <Button variant="secondary" on:click={() => isOpen = false}>Отмена</Button>
    <Button variant="danger" on:click={handleConfirm}>Удалить</Button>
  </svelte:fragment>
</Modal>
```

---

## 6. Стилизация

### Tailwind CSS

Проект использует Tailwind. Не писать кастомный CSS без необходимости.

```svelte
<!-- правильно -->
<div class="flex flex-col gap-3 p-4">

<!-- не надо -->
<div style="display: flex; flex-direction: column; gap: 12px; padding: 16px;">
```

### Цвета и тема Telegram

Telegram передаёт переменные темы (светлая / тёмная). Получать через CSS-переменные, которые автоматически обновляются при смене темы:

```css
/* Telegram-токены, доступные глобально */
var(--tg-theme-bg-color)
var(--tg-theme-text-color)
var(--tg-theme-hint-color)
var(--tg-theme-link-color)
var(--tg-theme-button-color)
var(--tg-theme-button-text-color)
var(--tg-theme-secondary-bg-color)
```

В Tailwind использовать через `bg-[var(--tg-theme-bg-color)]` или настроить алиасы в `tailwind.config.js`:

```js
// tailwind.config.js
theme: {
  extend: {
    colors: {
      'tg-bg': 'var(--tg-theme-bg-color)',
      'tg-text': 'var(--tg-theme-text-color)',
      'tg-btn': 'var(--tg-theme-button-color)',
      'tg-btn-text': 'var(--tg-theme-button-text-color)',
      'tg-secondary': 'var(--tg-theme-secondary-bg-color)',
      'tg-hint': 'var(--tg-theme-hint-color)',
    },
  },
}
```

Использование:
```svelte
<div class="bg-tg-bg text-tg-text">
  <button class="bg-tg-btn text-tg-btn-text">Действие</button>
</div>
```

### Мобильная верстка

- Минимальный touch target — 44×44px
- Отступы по краям экрана: `px-4`
- Фиксированный bottom bar (NavBar): учитывать через `pb-safe` или `padding-bottom: env(safe-area-inset-bottom)`

---

## 7. Обработка ошибок

### Стратегия

| Тип ошибки | Где обрабатывается | Что показывается |
|------------|-------------------|-----------------|
| Нет сети | TanStack Query `isError` | `ErrorScreen` с кнопкой "Повторить" |
| 5xx сервер | TanStack Query `isError` | `ErrorScreen` с кнопкой "Повторить" |
| 401 (истёк токен) | API-клиент, глобально | Редирект на `/auth` |
| 403 (нет прав) | Guard-компонент | `ErrorScreen` "Нет доступа" |
| 404 (не найдено) | TanStack Query `isError` | `ErrorScreen` "Не найдено" |
| Ошибка формы (422) | `createMutation.onError` | inline-ошибка под полем |
| Workspace suspended | Проверка при входе в workspace | Отдельный экран (см. `screens_error.md`) |

### Определение типа ошибки

```ts
// src/api/client.ts
export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public detail?: unknown,
  ) {
    super(message)
  }
}
```

```svelte
<script lang="ts">
  import { ApiError } from '@/api/client'

  const query = createWorkspacesQuery()

  $: errorMessage = (() => {
    if (!$query.error) return null
    if ($query.error instanceof ApiError) {
      if ($query.error.status === 404) return 'Пространство не найдено'
      if ($query.error.status === 403) return 'Нет доступа'
    }
    return 'Что-то пошло не так'
  })()
</script>
```

### Глобальный интерцептор 401

```ts
// src/api/client.ts
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })

  if (response.status === 401) {
    authStore.clear()
    window.location.href = '/auth'
    throw new ApiError(401, 'Unauthorized')
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new ApiError(response.status, response.statusText, detail)
  }

  return response.json()
}
```

---

## 8. Типы и DTO

Все общие типы — в `src/lib/types.ts`. Не дублировать определения.

```ts
// src/lib/types.ts

export type WorkspaceStatus = 'active' | 'suspended' | 'archived'
export type WorkspacePlan = 'free' | 'basic' | 'pro' | 'business'
export type WorkspaceRole = 'super_admin' | 'workspace_admin' | 'assistant' | 'client'

export interface User {
  id: string
  full_name: string
  username: string | null
  is_super_admin: boolean
}

export interface Workspace {
  id: string
  title: string
  slug: string
  status: WorkspaceStatus
  plan: WorkspacePlan
  fee_rate: number
  created_at: string
}

export interface WorkspaceMembership {
  workspace: Workspace
  role: WorkspaceRole
}

// DTO для запросов
export interface CreateWorkspaceDto {
  title: string
  slug: string
  admin_telegram_id?: number
}

export interface PatchWorkspaceDto {
  title?: string
  status?: WorkspaceStatus
}
```

---

## 9. Работа с Telegram SDK

### Кнопка "Назад"

Telegram показывает нативную кнопку назад в шапке. Управлять ею явно:

```svelte
<script lang="ts">
  import { useBackButton } from '@tma.js/sdk-svelte'
  import { goto } from '$app/navigation'

  const backButton = useBackButton()

  backButton.show()
  backButton.on('click', () => goto('/workspace-select'))

  // убрать кнопку при уничтожении компонента
  onDestroy(() => {
    backButton.hide()
    backButton.off('click')
  })
</script>
```

**Правило:** показывать кнопку "Назад" на всех экранах, кроме главных (dashboard, workspace-select).

### Главная кнопка (MainButton)

Использовать для основного действия на экране вместо кнопки внутри контента:

```svelte
<script lang="ts">
  import { useMainButton } from '@tma.js/sdk-svelte'

  const mainButton = useMainButton()

  $: {
    if (isFormValid) {
      mainButton.setText('Создать')
      mainButton.enable()
    } else {
      mainButton.setText('Заполните форму')
      mainButton.disable()
    }
  }

  mainButton.show()
  mainButton.on('click', handleSubmit)

  onDestroy(() => {
    mainButton.hide()
    mainButton.off('click')
  })
</script>
```

**Когда использовать:** формы создания/редактирования. Не использовать на экранах-списках.

### Вибрация (HapticFeedback)

Добавлять тактильный отклик на ключевые действия:

```ts
import { useHapticFeedback } from '@tma.js/sdk-svelte'

const haptic = useHapticFeedback()

// при успешном действии
haptic.notificationOccurred('success')

// при ошибке
haptic.notificationOccurred('error')

// при нажатии на кнопку (лёгкий)
haptic.impactOccurred('light')
```

### Открытие внешних ссылок

```ts
import { useUtils } from '@tma.js/sdk-svelte'

const utils = useUtils()

// открыть Telegram-профиль
utils.openTelegramLink('https://t.me/username')

// открыть внешний сайт (через in-app браузер)
utils.openLink('https://example.com')
```

Не использовать `window.open()` — не работает корректно в Telegram.
