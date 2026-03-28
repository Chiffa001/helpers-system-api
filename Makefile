COMPOSE = docker compose

.PHONY: up down logs migrate dev

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	uv run alembic upgrade head

dev:
	uv run fastapi dev
