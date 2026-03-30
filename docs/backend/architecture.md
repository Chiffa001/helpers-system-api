# Architecture

## Stack
- FastAPI
- PostgreSQL
- Redis
- ARQ (фоновые задачи: истечение счетов, обработка webhook)
- Svelte (Mini App)
- React (future admin)

---

## Компоненты
- API
- DB (multi-tenant: все таблицы содержат workspace_id)
- Payment layer (CryptoBot)
- Telegram Bot (один бот или по боту на workspace — см. ниже)
- Background workers (ARQ)

---

## Multi-tenancy

Модель: shared database, shared schema.

Каждая таблица содержит workspace_id. Изоляция данных обеспечивается на уровне middleware:
1. JWT содержит `sub` (user UUID) и `is_super_admin` (bool)
2. `get_current_user` декодирует токен, загружает пользователя из DB, проверяет `is_active`
3. `require_workspace_access` проверяет активную запись `WorkspaceMember` для запрашиваемого workspace
4. Все запросы к DB фильтруются по workspace_id

Super admin (`is_super_admin=True`) обходит проверку членства — получает доступ ко всем workspace-ам с виртуальной ролью `"super_admin"`.

---

## Telegram Bot

Два варианта (выбирается при развертывании):

Вариант 1: один бот для всех workspace-ов
- клиент указывает workspace slug при старте
- бот открывает Mini App с нужным контекстом

Вариант 2: отдельный бот на workspace (рекомендуется для продакшена)
- каждый workspace регистрирует своего бота
- бот всегда открывает Mini App в контексте своего workspace
- более чистый UX для клиентов

---

## Поток авторизации

1. Telegram Mini App получает `initData` от Telegram WebApp SDK
2. Mini App отправляет `POST /auth/telegram`:
   - заголовок `X-TG-HASH: <initData строка>`
   - тело: `{ user: { id, first_name, last_name, username }, auth_date, hash, query_id? }`
3. Backend проверяет HMAC-SHA256 подпись initData (ключ: `HMAC(WebAppData, BOT_TOKEN)`), TTL не более 24 часов
4. Пользователь upsert-ится по `telegram_id`; если `telegram_id == SUPER_ADMIN_TELEGRAM_ID` — `is_super_admin=True`
5. Возвращается JWT (HS256, claims: `sub`, `is_super_admin`, `exp`) и профиль пользователя
6. Дальнейшие запросы: `Authorization: Bearer <token>`, middleware проверяет токен и членство в workspace
7. payments -> webhook -> background worker -> подтверждение

---

## Redis

Используется для:
- очередь фоновых задач (ARQ)
- rate limiting

---

## Крипто-платежи

Провайдер: CryptoBot (api.cryptobot.app)

Поддерживаемые валюты: TON, USDT

Flow:
1. создать invoice через CryptoBot API
2. показать пользователю ссылку или QR
3. CryptoBot отправляет webhook при оплате
4. backend проверяет подпись webhook
5. обновляет статус invoice и payment

Важно: webhook обрабатывается идемпотентно (повторные запросы безопасны)

---

## Биллинг платформы

Модуль billing работает поверх модуля payments и срабатывает при каждом успешном платеже клиента.

Flow удержания комиссии:
1. payment webhook подтверждает оплату invoice
2. billing middleware проверяет план workspace
3. если plan = free → вычисляется fee = amount × fee_rate, создается PlatformFee
4. если plan != free (активная подписка) → комиссия не удерживается
5. расчет идет в фоновой задаче (ARQ), не блокирует ответ клиенту

Подписки обрабатываются отдельно от клиентских платежей.
Провайдер для оплаты подписок: на усмотрение (Stripe, ЮKassa, или ручная оплата на старте).

---

## Модули
- auth
- workspaces
- billing (subscription, fees)
- users
- projects
- events
- care_programs
- invoices
- payments
- background (workers)
