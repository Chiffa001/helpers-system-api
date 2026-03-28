# helpers-system-api

Backend for Helpers System Mini App.

## Environment

```bash
export DATABASE_URL="postgresql+asyncpg://helpers:helpers@localhost:5433/helpers_system"
export REDIS_URL="redis://localhost:6379"
export JWT_SECRET="replace-with-random-secret"
export JWT_EXPIRE_HOURS="24"
export TELEGRAM_BOT_TOKEN="telegram-bot-token"
export SUPER_ADMIN_TELEGRAM_ID="123456789"
```

## Infrastructure

```bash
docker compose up -d
```

## Run

```bash
uv sync
uv run fastapi dev
```

## Migrations

```bash
uv run alembic upgrade head
```

## Implemented Step 0 Backend Scope

- Async PostgreSQL via SQLAlchemy
- Telegram Mini App auth with JWT exchange
- Users, workspaces, workspace members
- Workspace membership and super admin access checks
- Alembic initial migration for step 0 tables
