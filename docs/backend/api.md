# API

Все эндпоинты, работающие с данными конкретного workspace, содержат workspace_id в пути:
`/workspaces/{workspaceId}/...`

Контекст текущего пользователя и его роль в workspace проверяются в middleware на основе JWT.

---

## Auth

### POST /auth/telegram
Аутентификация через Telegram Mini App. Принимает Telegram initData и возвращает JWT.

**Headers:**
- `X-TG-HASH: <initData>` — строка initData из Telegram WebApp SDK (обязательно)

**Body:**
```json
{
  "user": { "id": 123456789, "first_name": "Ivan", "last_name": "Ivanov", "username": "ivan" },
  "auth_date": 1711800000,
  "hash": "abc123...",
  "query_id": "optional"
}
```

**Response:**
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "user": { "id": "<uuid>", "full_name": "Ivan Ivanov", "username": "ivan", "is_super_admin": false }
}
```

Валидация: HMAC-SHA256 подпись initData с ключом `HMAC(WebAppData, BOT_TOKEN)`, TTL 24 часа.
Новый пользователь создаётся автоматически. Если `is_active=false` — 403.

---

### GET /auth/me
Возвращает профиль текущего пользователя по Bearer-токену.

---

### GET /auth/me/workspaces
Список активных workspace-ов пользователя с его ролью в каждом (`workspace_admin` / `assistant` / `client`).

---

## Workspaces
GET /workspaces                  ← super_admin: все; остальные: свои
POST /workspaces                 ← super_admin
GET /workspaces/{id}
PATCH /workspaces/{id}           ← workspace_admin, super_admin
DELETE /workspaces/{id}          ← super_admin

GET /workspaces/{id}/members
POST /workspaces/{id}/members    ← пригласить пользователя в workspace
PATCH /workspaces/{id}/members/{userId}   ← изменить роль
DELETE /workspaces/{id}/members/{userId}  ← исключить

---

## Client Applications
POST /workspaces/{workspaceId}/client-applications
GET /workspaces/{workspaceId}/client-applications
GET /workspaces/{workspaceId}/client-applications/{id}
POST /workspaces/{workspaceId}/client-applications/{id}/create-first-invoice

---

## Users (внутри workspace)
GET /workspaces/{workspaceId}/users
GET /workspaces/{workspaceId}/users/{id}

---

## Projects
GET /workspaces/{workspaceId}/projects
POST /workspaces/{workspaceId}/projects
GET /workspaces/{workspaceId}/projects/{id}
PATCH /workspaces/{workspaceId}/projects/{id}
DELETE /workspaces/{workspaceId}/projects/{id}

POST /workspaces/{workspaceId}/projects/{id}/clients
POST /workspaces/{workspaceId}/projects/{id}/assistants
PATCH /workspaces/{workspaceId}/projects/{id}/members/{memberId}
DELETE /workspaces/{workspaceId}/projects/{id}/members/{memberId}

GET /workspaces/{workspaceId}/projects/{id}/progress

---

## Events
GET /workspaces/{workspaceId}/events
POST /workspaces/{workspaceId}/events
GET /workspaces/{workspaceId}/events/{id}
PATCH /workspaces/{workspaceId}/events/{id}
DELETE /workspaces/{workspaceId}/events/{id}

GET /workspaces/{workspaceId}/events/{id}/participants
POST /workspaces/{workspaceId}/events/{id}/join-free
POST /workspaces/{workspaceId}/events/{id}/create-invoice

---

## Care Programs
GET /workspaces/{workspaceId}/care-programs
POST /workspaces/{workspaceId}/care-programs
GET /workspaces/{workspaceId}/care-programs/{id}
PATCH /workspaces/{workspaceId}/care-programs/{id}
DELETE /workspaces/{workspaceId}/care-programs/{id}

GET /workspaces/{workspaceId}/projects/{id}/care-programs

---

## Care Steps
GET /workspaces/{workspaceId}/care-steps
POST /workspaces/{workspaceId}/care-steps
GET /workspaces/{workspaceId}/care-steps/{id}
PATCH /workspaces/{workspaceId}/care-steps/{id}
DELETE /workspaces/{workspaceId}/care-steps/{id}

---

## Invoices
GET /workspaces/{workspaceId}/invoices
POST /workspaces/{workspaceId}/invoices
GET /workspaces/{workspaceId}/invoices/{id}
PATCH /workspaces/{workspaceId}/invoices/{id}/cancel

POST /workspaces/{workspaceId}/invoices/{id}/pay-crypto
POST /workspaces/{workspaceId}/invoices/{id}/pay-link

---

## Payments
POST /payments/webhook           ← без workspace в пути, webhook от CryptoBot

---

## Billing (workspace)
GET /workspaces/{workspaceId}/billing                     ← текущий тариф, дата продления, статус
GET /workspaces/{workspaceId}/billing/subscription        ← детали подписки
POST /workspaces/{workspaceId}/billing/subscription       ← оформить/обновить подписку
DELETE /workspaces/{workspaceId}/billing/subscription     ← отменить подписку

GET /workspaces/{workspaceId}/billing/fees                ← история удержанных комиссий

---

## Super Admin
GET /admin/workspaces
POST /admin/workspaces
PATCH /admin/workspaces/{id}
DELETE /admin/workspaces/{id}
PATCH /admin/workspaces/{id}/plan                         ← вручную изменить тариф

GET /admin/users
PATCH /admin/users/{id}

GET /admin/billing/fees                                   ← все комиссии по всем workspace-ам
GET /admin/billing/revenue                                ← общая выручка платформы

---

## Workspace Admin
GET /workspaces/{workspaceId}/admin/users
PATCH /workspaces/{workspaceId}/admin/users/{id}/role
GET /workspaces/{workspaceId}/admin/client-applications
POST /workspaces/{workspaceId}/admin/client-applications/{id}/approve
POST /workspaces/{workspaceId}/admin/client-applications/{id}/reject
POST /workspaces/{workspaceId}/admin/invoices/{id}/confirm
