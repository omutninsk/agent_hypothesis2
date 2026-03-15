.PHONY: up down logs build migrate clean rebuild shell

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

migrate:
	docker compose run --rm app alembic upgrade head

clean:
	docker compose down -v

rebuild: clean up

shell:
	docker compose exec app bash
