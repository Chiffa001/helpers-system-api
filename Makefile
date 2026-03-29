COMPOSE = docker compose

.PHONY: up down logs migrate dev lint format typecheck test ci install-hooks

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	uv run alembic upgrade head

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile ./certs/192.168.0.15+2-key.pem --ssl-certfile ./certs/192.168.0.15+2.pem --reload


lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy app/

test:
	uv run pytest -m "not integration"

test-all:
	uv run pytest -m "integration or not integration"

ci: lint typecheck test

install-hooks:
	uv run pre-commit install
