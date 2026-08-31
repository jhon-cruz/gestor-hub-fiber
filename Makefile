.DEFAULT_GOAL := help

.PHONY: help init-env dev stop logs status migrate downgrade test create-admin validate-config

help:
	@echo "Gestor Hub Fiber"
	@echo "  make dev           inicia API e PostGIS em http://localhost:3030"
	@echo "  make init-env      gera .env local com segredos aleatórios"
	@echo "  make stop          encerra os containers"
	@echo "  make logs          acompanha os logs"
	@echo "  make status        mostra o estado dos containers"
	@echo "  make migrate       aplica migrations"
	@echo "  make downgrade     reverte uma migration"
	@echo "  make test          executa testes de API/RBAC"
	@echo "  make create-admin  cria o primeiro administrador interativamente"

validate-config:
	@test -f .env || { echo "Crie .env a partir de .env.example"; exit 1; }
	@docker compose config --quiet

init-env:
	@./scripts/init-env

dev: validate-config
	docker compose up --build -d db migration api

stop:
	docker compose down

logs:
	docker compose logs -f api migration db

status:
	docker compose ps

migrate: validate-config
	docker compose run --rm migration

downgrade: validate-config
	docker compose run --rm migration alembic downgrade -1

test: validate-config
	docker compose --profile test run --build --rm test

create-admin: validate-config
	docker compose exec api python -m app.cli create-user --role admin
