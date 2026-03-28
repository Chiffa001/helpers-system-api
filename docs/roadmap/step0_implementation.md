# Этап 0 — Детальное задание на реализацию

Покрывает: auth, роли, workspace, WorkspaceMember, выбор workspace при входе.

---

## Backend

### 1. База данных

#### Миграции (в порядке применения)

**1.1 Таблица `users`**
```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id   BIGINT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    username      TEXT,
    is_super_admin BOOLEAN NOT NULL DEFAULT false,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**1.2 Таблица `workspaces`**
```sql
CREATE TABLE workspaces (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title              TEXT NOT NULL,
    slug               TEXT UNIQUE NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'suspended', 'archived')),
    plan               TEXT NOT NULL DEFAULT 'free'
                           CHECK (plan IN ('free', 'basic', 'pro', 'business')),
    fee_rate           NUMERIC(5,4) NOT NULL DEFAULT 0.03,
    created_by_user_id UUID REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workspaces_slug ON workspaces(slug);
CREATE INDEX idx_workspaces_status ON workspaces(status);
```

**1.3 Таблица `workspace_members`**
```sql
CREATE TABLE workspace_members (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('workspace_admin', 'assistant', 'client')),
    is_active    BOOLEAN NOT NULL DEFAULT true,
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id)
);

CREATE INDEX idx_wm_workspace ON workspace_members(workspace_id);
CREATE INDEX idx_wm_user ON workspace_members(user_id);
```

---

### 2. Auth

#### POST /auth/telegram

**Назначение:** обменять Telegram `initData` на JWT.

**Алгоритм:**
1. Получить `initData` из тела запроса
2. Верифицировать подпись HMAC-SHA256 согласно документации Telegram Mini App
3. Распарсить `user` из `initData`
4. Найти или создать `User` по `telegram_id` (upsert: обновить `full_name`, `username`)
5. Сгенерировать JWT: `{ sub: user.id, is_super_admin: bool, exp: now + 24h }`
6. Вернуть токен и данные пользователя

**Request:**
```json
{
  "init_data": "query_id=...&user=...&auth_date=...&hash=..."
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "full_name": "Иван Петров",
    "username": "ivanpetrov",
    "is_super_admin": false
  }
}
```

**Ошибки:**
- `401` — невалидная подпись initData
- `403` — пользователь заблокирован (`is_active = false`)

---

#### GET /auth/me

**Назначение:** получить данные текущего пользователя.

**Response 200:**
```json
{
  "id": "uuid",
  "full_name": "Иван Петров",
  "username": "ivanpetrov",
  "is_super_admin": false
}
```

---

#### GET /auth/me/workspaces

**Назначение:** список workspace-ов пользователя с его ролью в каждом.

**Response 200:**
```json
[
  {
    "workspace": {
      "id": "uuid",
      "title": "Агентство Иванова",
      "slug": "ivanov-agency",
      "status": "active",
      "plan": "pro"
    },
    "role": "workspace_admin"
  },
  {
    "workspace": {
      "id": "uuid",
      "title": "Клиника Бета",
      "slug": "clinic-beta",
      "status": "active",
      "plan": "free"
    },
    "role": "client"
  }
]
```

---

### 3. Workspaces

#### Middleware: проверка членства

Для всех эндпоинтов вида `/workspaces/{workspaceId}/...`:

1. Извлечь `user_id` из JWT
2. Проверить `is_super_admin` — если true, пропустить проверку, установить роль `super_admin`
3. Найти `WorkspaceMember` по `(workspace_id, user_id, is_active=true)`
4. Если не найден — вернуть `403 Forbidden`
5. Прикрепить роль к контексту запроса

---

#### GET /workspaces

- `super_admin`: возвращает все workspace-ы с поддержкой фильтров `?status=active`
- остальные: возвращает только workspace-ы, где пользователь является членом

**Query params:** `status` (опционально)

**Response 200:**
```json
[
  {
    "id": "uuid",
    "title": "Агентство Иванова",
    "slug": "ivanov-agency",
    "status": "active",
    "plan": "free",
    "created_at": "2026-01-15T10:00:00Z"
  }
]
```

---

#### POST /workspaces

**Доступ:** только `super_admin`

**Request:**
```json
{
  "title": "Агентство Иванова",
  "slug": "ivanov-agency",
  "admin_telegram_id": 123456789
}
```

**Алгоритм:**
1. Проверить уникальность `slug`
2. Создать `Workspace`
3. Если передан `admin_telegram_id` — найти пользователя и создать `WorkspaceMember` с ролью `workspace_admin`
4. Вернуть созданный workspace

**Ошибки:**
- `409` — slug уже занят
- `404` — пользователь с таким telegram_id не найден

---

#### GET /workspaces/{id}

**Доступ:** член workspace или super_admin

**Response 200:**
```json
{
  "id": "uuid",
  "title": "Агентство Иванова",
  "slug": "ivanov-agency",
  "status": "active",
  "plan": "free",
  "fee_rate": 0.03,
  "created_at": "2026-01-15T10:00:00Z",
  "members_count": {
    "workspace_admin": 1,
    "assistant": 3,
    "client": 12
  }
}
```

---

#### PATCH /workspaces/{id}

**Доступ:** `workspace_admin` или `super_admin`

**Request (все поля опциональны):**
```json
{
  "title": "Новое название",
  "status": "suspended"
}
```

Slug изменить нельзя. Попытка передать `slug` — игнорируется.

---

#### GET /workspaces/{id}/members

**Доступ:** `workspace_admin` или `super_admin`

**Response 200:**
```json
[
  {
    "id": "uuid",
    "user": {
      "id": "uuid",
      "full_name": "Мария Сидорова",
      "username": "maria_s"
    },
    "role": "assistant",
    "is_active": true,
    "joined_at": "2026-02-01T09:00:00Z"
  }
]
```

---

#### POST /workspaces/{id}/members

**Доступ:** `workspace_admin` или `super_admin`

**Request:**
```json
{
  "telegram_id": 987654321,
  "role": "assistant"
}
```

**Алгоритм:**
1. Найти пользователя по `telegram_id` (если нет — вернуть 404)
2. Проверить, что пользователь не является уже активным членом (если уже член — 409)
3. Создать `WorkspaceMember`

**Ошибки:**
- `404` — пользователь не найден
- `409` — уже является членом workspace

---

#### PATCH /workspaces/{id}/members/{userId}

**Доступ:** `workspace_admin` или `super_admin`

**Request:**
```json
{
  "role": "workspace_admin",
  "is_active": false
}
```

---

#### DELETE /workspaces/{id}/members/{userId}

**Доступ:** `workspace_admin` или `super_admin`

Устанавливает `is_active = false`. Данные не удаляются.
Нельзя удалить самого себя.

---

### 4. Инициализация super_admin

При первом запуске системы нужно создать первого super_admin вручную:

```sql
UPDATE users SET is_super_admin = true WHERE telegram_id = <ваш_telegram_id>;
```

Либо через переменную окружения `SUPER_ADMIN_TELEGRAM_ID` при старте:
- при инициализации БД скрипт создаёт/обновляет запись

---

### 5. Переменные окружения

```
DATABASE_URL=postgresql://user:pass@localhost:5432/bergantino
REDIS_URL=redis://localhost:6379
JWT_SECRET=<random_256bit>
JWT_EXPIRE_HOURS=24
TELEGRAM_BOT_TOKEN=<token>
SUPER_ADMIN_TELEGRAM_ID=<telegram_id>
```

---

### 6. Структура модулей FastAPI

```
app/
├── main.py
├── core/
│   ├── config.py          # переменные окружения
│   ├── database.py        # подключение к PostgreSQL
│   ├── redis.py           # подключение к Redis
│   └── security.py        # JWT: создание и верификация
├── middleware/
│   ├── auth.py            # извлечение user из JWT
│   └── workspace.py       # проверка членства в workspace
├── modules/
│   ├── auth/
│   │   ├── router.py
│   │   ├── service.py     # верификация initData, upsert user
│   │   └── schemas.py
│   └── workspaces/
│       ├── router.py
│       ├── service.py
│       ├── schemas.py
│       └── models.py      # SQLAlchemy ORM модели
└── migrations/            # Alembic
```

---

## Frontend

### 1. Пакет для работы с Telegram Mini App

Используется `@tma.js/sdk-svelte` — официальный SDK для Svelte с реактивными обёртками над Telegram WebApp API.

**Установка:** уже добавлен в зависимости (`npm install @tma.js/sdk-svelte`).

**Инициализация** — один раз в корневом компоненте `app.svelte`:

```svelte
<script lang="ts">
  import { init, retrieveLaunchParams } from '@tma.js/sdk-svelte'

  init()
  const launchParams = retrieveLaunchParams()
</script>
```

**Что использовать из SDK:**

| Что нужно | Как получить |
|---|---|
| `initData` для отправки на backend | `retrieveLaunchParams().initDataRaw` |
| Данные пользователя Telegram | `retrieveLaunchParams().initData.user` |
| Управление кнопкой назад | `useBackButton()` |
| Главная кнопка (MainButton) | `useMainButton()` |
| Тема оформления | `useMiniApp()` → `colorScheme` |
| Закрыть приложение | `useMiniApp()` → `close()` |
| Открыть ссылку | `useUtils()` → `openTelegramLink()` |

**Получение `initDataRaw` для авторизации:**

```ts
import { retrieveLaunchParams } from '@tma.js/sdk-svelte'

const { initDataRaw } = retrieveLaunchParams()
// Отправить initDataRaw в POST /auth/telegram
```

**Проверка, что приложение запущено в Telegram:**

```ts
import { retrieveLaunchParams } from '@tma.js/sdk-svelte'

try {
  const params = retrieveLaunchParams()
  // всё ок, работаем в Telegram
} catch {
  // запущено не в Telegram — показать заглушку
}
```

**Реактивные компоненты (пример MainButton):**

```svelte
<script lang="ts">
  import { useMainButton } from '@tma.js/sdk-svelte'

  const mainButton = useMainButton()
  mainButton.setText('Создать')
  mainButton.enable()
  mainButton.show()
  mainButton.on('click', handleSubmit)
</script>
```

---

### 2. Архитектура состояния

Добавить Svelte store для глобального контекста:

```
src/stores/
├── auth.ts          # текущий пользователь + JWT токен
└── workspace.ts     # активный workspace + роль пользователя в нём
```

**`auth.ts`**
```ts
interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
}
```

**`workspace.ts`**
```ts
interface WorkspaceState {
  active: Workspace | null
  role: 'super_admin' | 'workspace_admin' | 'assistant' | 'client' | null
  list: WorkspaceMembership[]
  isLoading: boolean
}
```

---

### 3. Роутинг

```
/                          → редирект: если не авторизован → /auth, иначе → /workspace-select или /dashboard
/auth                      → экран авторизации (обработка initData)
/workspace-select          → экран выбора workspace (если workspace > 1)
/workspace/:slug/          → главная текущего workspace (dashboard)
/workspace/:slug/settings  → настройки workspace (workspace_admin)
/admin/workspaces          → список всех workspace-ов (super_admin)
/admin/workspaces/new      → создание workspace (super_admin)
/admin/workspaces/:id      → управление workspace (super_admin)
```

---

### 4. API клиент и data-fetching

#### 4.1 Базовый HTTP-клиент

Создать fetch-wrapper с:
- автоматической подстановкой `Authorization: Bearer <token>` из store
- интерцептором 401 → сброс токена → редирект на /auth
- базовым URL из переменной окружения `VITE_API_URL`

```
src/api/
├── client.ts        # базовый fetch-wrapper
├── auth.ts          # /auth/telegram, /auth/me, /auth/me/workspaces
└── workspaces.ts    # CRUD workspace, members
```

#### 4.2 TanStack Query (`@tanstack/svelte-query`)

Используется для всех запросов к API: кэширование, фоновое обновление, состояния загрузки и ошибок.

**Установка:** уже добавлен в зависимости (`npm install @tanstack/svelte-query`).

**Инициализация** — в корневом компоненте `app.svelte`:

```svelte
<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query'

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60,       // 1 минута до повторного запроса
        retry: 1,
      },
    },
  })
</script>

<QueryClientProvider client={queryClient}>
  <slot />
</QueryClientProvider>
```

**Правила использования:**

| Операция | Хук |
|---|---|
| Загрузить данные (GET) | `createQuery` |
| Создать / обновить / удалить | `createMutation` |
| Сбросить кэш после мутации | `queryClient.invalidateQueries` |

**Пример запроса списка workspace-ов:**

```ts
// src/api/workspaces.ts
export function createWorkspacesQuery() {
  return createQuery({
    queryKey: ['workspaces'],
    queryFn: () => apiClient.get('/auth/me/workspaces'),
  })
}
```

```svelte
<script lang="ts">
  import { createWorkspacesQuery } from '@/api/workspaces'

  const query = createWorkspacesQuery()
</script>

{#if $query.isLoading}
  <Skeleton />
{:else if $query.isError}
  <ErrorMessage />
{:else}
  {#each $query.data as item}
    <WorkspaceCard {item} />
  {/each}
{/if}
```

**Пример мутации (создание workspace):**

```ts
// src/api/workspaces.ts
export function createWorkspaceMutation() {
  const queryClient = useQueryClient()
  return createMutation({
    mutationFn: (data: CreateWorkspaceDto) =>
      apiClient.post('/workspaces', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })
}
```

**Query keys — соглашение:**

```ts
['workspaces']                          // список всех
['workspaces', workspaceId]             // один workspace
['workspaces', workspaceId, 'members']  // члены workspace
['me', 'workspaces']                    // workspaces текущего пользователя
```

---

### 5. Экраны к реализации

#### 5.1 Авторизация (`/auth`)

**Что делает:**
1. При монтировании вызывает `retrieveLaunchParams()` из `@tma.js/sdk-svelte`
2. Берёт `initDataRaw` и отправляет в `POST /auth/telegram`
3. Сохраняет токен и данные пользователя в store
4. Загружает список workspace-ов через `GET /auth/me/workspaces`
5. Редирект: один workspace → `/workspace/:slug`, несколько → `/workspace-select`

**Что показывает:**
- полноэкранный лоадер на время запроса
- если `retrieveLaunchParams()` бросает исключение (запуск вне Telegram) — заглушка "Откройте приложение через Telegram"
- если ошибка авторизации — сообщение об ошибке

---

#### 5.2 Выбор workspace (`/workspace-select`)

**Что делает:**
- отображает список из `workspace.list`
- при нажатии на карточку: устанавливает `workspace.active` и `workspace.role`, редирект на `/workspace/:slug`

**Компоненты:**
- `WorkspaceCard` — карточка с названием, ролью, статистикой
- состояние загрузки: скелетон
- пустое состояние: "Вы не подключены ни к одному пространству"

---

#### 5.3 Создание workspace (`/admin/workspaces/new`) — только super_admin

**Форма:**

| Поле | Компонент | Валидация |
|------|-----------|-----------|
| Название | TextInput | required, min 2 символа |
| Slug | TextInput | required, `/^[a-z0-9-]+$/`, уникальность через API |
| Telegram ID администратора | TextInput | опционально, только цифры |

Slug автозаполняется из названия через транслитерацию при изменении поля названия (если slug не редактировался вручную).

**Поведение кнопки "Создать":**
- задизейблена до заполнения обязательных полей
- spinner во время запроса
- после успеха: редирект на `/admin/workspaces/:id` + toast "Пространство создано"
- при ошибке slug: inline-ошибка под полем

---

#### 5.4 Список workspace-ов (`/admin/workspaces`) — только super_admin

- загрузка через `GET /workspaces?status=...`
- фильтры по статусу: All / Active / Suspended / Archived
- счётчик
- переход на карточку по клику

---

#### 5.5 Управление workspace (`/admin/workspaces/:id`) — только super_admin

- загрузка через `GET /workspaces/:id` и `GET /workspaces/:id/members`
- редактирование названия и статуса через `PATCH /workspaces/:id`
- добавление admin-а через `POST /workspaces/:id/members`
- изменение/удаление члена через `PATCH` / `DELETE`
- опасная зона: приостановить / архивировать с подтверждением

---

#### 5.6 Настройки workspace (`/workspace/:slug/settings`) — workspace_admin

Аналогично п.4.5, но ограничено текущим workspace и без опасной зоны.

---

### 6. Защита роутов

```ts
// Правила доступа:
/auth                  → только неавторизованные
/workspace-select      → только авторизованные
/workspace/:slug/*     → авторизован + член данного workspace
/admin/*               → is_super_admin === true
/workspace/:slug/settings → роль === 'workspace_admin' || is_super_admin
```

Guard-компонент проверяет store при монтировании и редиректит при нарушении.

---

### 7. Переменные окружения

```
VITE_API_URL=https://localhost:8000
VITE_APP_ENV=development
```

---

## Критерии готовности Этапа 0

### Backend
- [ ] Миграции применены, таблицы созданы
- [ ] `POST /auth/telegram` верифицирует initData и возвращает JWT
- [ ] `GET /auth/me/workspaces` возвращает список с ролями
- [ ] CRUD workspace работает с проверкой прав
- [ ] Membership: добавление, изменение роли, деактивация
- [ ] Middleware отклоняет запросы без членства в workspace
- [ ] super_admin обходит workspace-проверку
- [ ] Первый super_admin создан через seed/env

### Frontend
- [ ] `@tma.js/sdk-svelte` инициализирован в корневом компоненте
- [ ] `QueryClientProvider` обёртывает приложение, `QueryClient` настроен
- [ ] `initDataRaw` корректно получается через `retrieveLaunchParams()`
- [ ] Авторизация проходит, токен сохраняется
- [ ] Экран выбора workspace отображает список и переключает контекст
- [ ] Роуты защищены по ролям
- [ ] Экраны создания/управления workspace работают (super_admin)
- [ ] Экран настроек workspace работает (workspace_admin)
- [ ] API-клиент подставляет токен и обрабатывает 401
