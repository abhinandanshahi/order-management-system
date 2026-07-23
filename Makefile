.PHONY: up down logs migrate test lint

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose run --rm api alembic upgrade head

test:
	docker compose run --rm api pytest -q

lint:
	docker compose run --rm api ruff check app tests
