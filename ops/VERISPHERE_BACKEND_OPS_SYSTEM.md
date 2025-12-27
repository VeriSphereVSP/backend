# VeriSphere Backend Ops System (Infrastructure-as-Code)

This document defines a **single, repeatable “ops bundle”** that installs, configures, and deploys the VeriSphere backend stack (including Postgres + Python services) onto a server. It is designed so you can **rebuild or redeploy** a server by re-running the same commands with the same repo + `.env`.

This is intentionally **repository-backed** (checked into `VeriSphereVSP/backend`) so future tasks can modify the same system.

---

## What this “ops bundle” is

We’ll use a simple, durable pattern:

1) **Docker Compose** for the runtime topology (services, networking, volumes)  
2) **Makefile** for one-command workflows (bootstrap / up / migrate / backup / logs)  
3) **Postgres migrations** (SQL files, versioned)  
4) Optional: **Ansible** to install Docker + base packages on Debian servers (one-time bootstrap)

This keeps your deploy reproducible without forcing Kubernetes early.

---

## Where this belongs (backend repo)

Create this structure in **`VeriSphereVSP/backend`**:

```
backend/
  ops/
    compose/
      docker-compose.yml
      env.example
      Makefile
    postgres/
      init/
        00_create_roles.sql
        10_create_db.sql
      migrations/
        0001_semantic_dedupe_schema.sql
      backups/
        .gitkeep
    ansible/
      inventory.ini
      playbook.yml
      roles/
        docker/
          tasks/main.yml
  services/
    semantic_dedupe/
      Dockerfile
      pyproject.toml
      src/semantic_dedupe/...
      README.md
```

- `ops/compose/` is the **one place** you run commands from.
- `ops/postgres/migrations/` is where schema changes go.
- `services/*` is where app code lives.

---

## Core deployment artifact: `docker-compose.yml`

Create `backend/ops/compose/docker-compose.yml`:

```yaml
services:
  postgres:
    # pgvector enabled Postgres (recommended for semantic search)
    image: pgvector/pgvector:pg16
    container_name: verisphere_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_SUPERUSER}
      POSTGRES_PASSWORD: ${POSTGRES_SUPERPASS}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - verisphere_pgdata:/var/lib/postgresql/data
      # init scripts run ONLY on first boot when data dir is empty
      - ../postgres/init:/docker-entrypoint-initdb.d:ro
      # migrations mounted for Makefile-driven application
      - ../postgres/migrations:/migrations:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_SUPERUSER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 20

  semantic-dedupe:
    build:
      context: ../../services/semantic_dedupe
    container_name: verisphere_semantic_dedupe
    restart: unless-stopped
    environment:
      DATABASE_URL: ${DATABASE_URL}
      EMBEDDINGS_PROVIDER: ${EMBEDDINGS_PROVIDER:-openai}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      EMBEDDINGS_MODEL: ${EMBEDDINGS_MODEL:-text-embedding-3-large}
      LOG_LEVEL: ${LOG_LEVEL:-info}
      PORT: 8081
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${SEMANTIC_DEDUPE_PORT:-8081}:8081"

volumes:
  verisphere_pgdata:
```

---

## Environment file

Create `backend/ops/compose/env.example`:

```bash
# --- Postgres ---
POSTGRES_SUPERUSER=postgres
POSTGRES_SUPERPASS=change_me
POSTGRES_DB=verisphere
POSTGRES_PORT=5432

# App DB user (created by migrations)
POSTGRES_APP_USER=verisphere_app
POSTGRES_APP_PASS=change_me_app

# Used by services (semantic-dedupe)
DATABASE_URL=postgresql://verisphere_app:change_me_app@postgres:5432/verisphere

# --- Embeddings provider ---
EMBEDDINGS_PROVIDER=openai
OPENAI_API_KEY=
EMBEDDINGS_MODEL=text-embedding-3-large

# --- Service ports ---
SEMANTIC_DEDUPE_PORT=8081

LOG_LEVEL=info
```

On servers, copy `env.example` to `.env` and fill secrets:
- `backend/ops/compose/.env` (do **not** commit)

---

## One-command workflows: Makefile

Create `backend/ops/compose/Makefile`:

```make
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
```

---

## Postgres init + migrations

### Init scripts (first boot only)

Create `backend/ops/postgres/init/00_create_roles.sql`:

```sql
-- Keep init scripts minimal. Migrations handle roles/tables.
```

### Migration: semantic dedupe schema + app user

Create `backend/ops/postgres/migrations/0001_semantic_dedupe_schema.sql`:

```sql
BEGIN;

-- Create app role if missing
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verisphere_app') THEN
    CREATE ROLE verisphere_app LOGIN PASSWORD 'change_me_app';
  END IF;
END $$;

-- Ensure DB ownership/privs
GRANT CONNECT ON DATABASE verisphere TO verisphere_app;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS claims (
  claim_id           BIGSERIAL PRIMARY KEY,
  claim_text         TEXT NOT NULL,
  content_hash       TEXT NOT NULL UNIQUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OpenAI text-embedding-3-large => 3072 dims (adjust if you change model)
CREATE TABLE IF NOT EXISTS claim_embeddings (
  claim_id           BIGINT PRIMARY KEY REFERENCES claims(claim_id) ON DELETE CASCADE,
  embedding_model    TEXT NOT NULL,
  embedding          vector(3072) NOT NULL,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS claim_embeddings_ivfflat
ON claim_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMIT;
```

**Important:** do not hardcode passwords in committed migrations for production. For production, replace this with:
- role creation done manually once, or
- a templated migration process, or
- a separate secured bootstrap script.

(For dev, hardcoding is acceptable for speed.)

---

## Semantic Dedupe Service container (deployable skeleton)

Create `backend/services/semantic_dedupe/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .
EXPOSE 8081
CMD ["python", "-m", "semantic_dedupe.app"]
```

Create `backend/services/semantic_dedupe/src/semantic_dedupe/app.py`:

```python
import os
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="VeriSphere Semantic Dedupe")

@app.get("/health")
def health():
    return {"ok": True}

def main():
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("semantic_dedupe.app:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
```

This is the **ops-compatible** service shell; Task 4.1 logic goes into this service.

---

## Server bootstrap (Debian) with Ansible (optional)

Create `backend/ops/ansible/inventory.ini`:

```ini
[verisphere]
your.server.ip ansible_user=debian
```

Create `backend/ops/ansible/playbook.yml`:

```yaml
- hosts: verisphere
  become: true
  roles:
    - docker
```

Create `backend/ops/ansible/roles/docker/tasks/main.yml`:

```yaml
- name: Install prerequisites
  apt:
    name:
      - ca-certificates
      - curl
      - gnupg
      - lsb-release
    state: present
    update_cache: yes

- name: Add Docker GPG key
  shell: |
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  args:
    creates: /etc/apt/keyrings/docker.gpg

- name: Add Docker repo
  shell: |
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  args:
    creates: /etc/apt/sources.list.d/docker.list

- name: Install docker engine + compose plugin
  apt:
    name:
      - docker-ce
      - docker-ce-cli
      - containerd.io
      - docker-buildx-plugin
      - docker-compose-plugin
    state: present
    update_cache: yes

- name: Ensure docker is running
  service:
    name: docker
    state: started
    enabled: true
```

Run:

```bash
cd backend/ops/ansible
ansible-playbook -i inventory.ini playbook.yml
```

---

## Day-0 deploy (new server)

On the server:

```bash
git clone https://github.com/VeriSphereVSP/backend.git
cd backend/ops/compose

cp env.example .env
nano .env

make up
make migrate

curl http://localhost:8081/health
```

---

## Redeploy (after code changes)

```bash
cd backend
git pull
cd ops/compose
make up
make migrate
```

---

## Backups / restore

Backup:

```bash
cd backend/ops/compose
make backup
```

Restore:

```bash
cd backend/ops/compose
make restore FILE=../postgres/backups/verisphere_YYYYMMDD_HHMMSS.sql
```

---

## How this stays current

From now on, when we add backend services (indexer, API, workers), we will:
- add a service to `ops/compose/docker-compose.yml`
- add any DB schema changes to `ops/postgres/migrations/`
- update this runbook when needed

