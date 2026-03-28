# Models

## User
- id
- telegram_id
- full_name
- username nullable
- is_super_admin (default false)
- is_active (default true)
- created_at

Роль пользователя не хранится глобально. Она определяется через WorkspaceMember.

---

## Workspace
- id
- title
- slug (уникальный идентификатор, например "ivanov-agency")
- status (active | suspended | archived)
- plan (free | basic | pro | business)
- fee_rate (decimal, например 0.03 — используется если plan = free)
- created_by_user_id
- created_at

---

## WorkspaceSubscription
- id
- workspace_id
- plan (basic | pro | business)
- status (active | canceled | expired)
- started_at
- expires_at
- canceled_at nullable
- payment_reference nullable (внешний ID платежа)

---

## PlatformFee
- id
- workspace_id
- invoice_id
- original_amount
- fee_rate
- fee_amount
- currency
- created_at

---

## WorkspaceMember
- id
- workspace_id
- user_id
- role (workspace_admin | assistant | client)
- is_active (default true)
- joined_at

Один пользователь может быть членом нескольких workspace-ов с разными ролями.

---

## ClientApplication
- id
- workspace_id
- telegram_id
- full_name
- username
- phone nullable
- status (pending | awaiting_first_payment | paid | approved | rejected)
- linked_user_id nullable
- approved_by_admin_id nullable
- approved_at nullable
- created_at

---

## Project
- id
- workspace_id
- title
- status (active | archived)
- description
- created_by_admin_id
- created_at

---

## ProjectMember
- id
- project_id
- user_id
- member_type (client | assistant)
- project_role nullable
- specialization nullable (например: medicine | documents | general)
- access_scope nullable
- added_at

---

## Event
- id
- workspace_id
- project_id
- title
- description nullable
- date
- time nullable
- location nullable
- price nullable
- is_free
- created_by_user_id
- created_at

---

## EventParticipant
- event_id
- user_id
- status (confirmed_free | pending_payment | paid | canceled)

---

## CareProgram
- id
- workspace_id
- project_id
- title
- visibility_scope (all | per_client | per_direction)
- created_by_user_id
- created_at

---

## CareStep
- id
- program_id
- project_id
- client_user_id nullable
- assigned_assistant_user_id nullable
- direction nullable
- title
- description nullable
- amount nullable
- payment_status (unpaid | invoiced | paid)
- execution_status (pending | in_progress | done)
- order
- created_at

---

## Invoice
- id
- workspace_id
- project_id
- client_user_id nullable
- care_step_id nullable
- event_id nullable
- amount
- currency (RUB | TON | USDT)
- status (issued | pending_payment | paid | canceled | expired)
- payment_method (fiat | crypto) nullable
- due_date nullable
- created_at

---

## Payment
- id
- invoice_id
- amount
- currency
- tx_hash nullable
- status (pending | confirmed | failed | expired)
- payment_method (fiat | crypto)
- created_at
