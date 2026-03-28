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
1. JWT содержит user_id
2. Middleware проверяет, что пользователь является членом запрашиваемого workspace
3. Все запросы к DB фильтруются по workspace_id

Super admin не ограничен workspace_id — получает доступ ко всем данным.

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

## Поток

1. Telegram -> Mini App (с параметром workspace_id)
2. Mini App -> backend (initData + workspace_id)
3. backend -> auth (проверка initData подписи)
4. backend -> проверка членства в workspace
5. API calls с workspace-scoped запросами
6. payments -> webhook -> background worker -> подтверждение

---

## Redis

Используется для:
- кэширование сессий (telegram initData)
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
