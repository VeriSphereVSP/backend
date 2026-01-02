SHELL := /bin/bash

COMPOSE := docker compose
ENVFILE := .env

.PHONY: check-env up down restart logs ps build pull migrate psql backup restore

check-env:
	@test -f $(ENVFILE) || (echo "Missing $(ENVFILE). Copy env.example -> .env"; exit 1)

up: check-env
	$(COMPOSE) --env-file $(ENVFILE) up -d --build

down: check-env
	$(COMPOSE) --env-file $(ENVFILE) down

restart: check-env
	$(COMPOSE) --env-file $(ENVFILE) restart

logs: check-env
	$(COMPOSE) --env-file $(ENVFILE) logs -f --tail=200

ps: check-env
	$(COMPOSE) --env-file $(ENVFILE) ps

build: check-env
	$(COMPOSE) --env-file $(ENVFILE) build

pull: check-env
	$(COMPOSE) --env-file $(ENVFILE) pull

migrate: check-env
	$(COMPOSE) --env-file $(ENVFILE) exec -T postgres bash -lc 'for f in /migrations/*.sql; do echo "Applying $$f"; psql -U $$POSTGRES_USER -d $$POSTGRES_DB -f $$f; done'

psql: check-env
	$(COMPOSE) --env-file $(ENVFILE) exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

backup: check-env
	mkdir -p ../postgres/backups
	$(COMPOSE) --env-file $(ENVFILE) exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB > ../postgres/backups/verisphere_$$(date +%Y%m%d_%H%M%S).sql

restore: check-env
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=../postgres/backups/file.sql"; exit 1; fi
	cat "$(FILE)" | $(COMPOSE) --env-file $(ENVFILE) exec -T postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB
