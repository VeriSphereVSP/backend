#!/usr/bin/env bash
# VeriSphere backend helper functions
# Source this file from ~/.bashrc or ~/.bash_profile

_vsb_compose_dir() { echo "$HOME/verisphere/backend/ops/compose"; }
_vsb_compose_file() { echo "$(_vsb_compose_dir)/docker-compose.yml"; }
_vsb_env_file() { echo "$(_vsb_compose_dir)/.env"; }

_vsb_load_env() {
  local ENV_FILE="$(_vsb_env_file)"
  if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env missing at $ENV_FILE"
    return 1
  fi
  set -a
  source "$ENV_FILE"
  set +a
}

_vsb_run_migrations() {
  local COMPOSE_FILE="$(_vsb_compose_file)"
  echo "🗄️ running migrations"
  docker compose -f "$COMPOSE_FILE" exec -T postgres bash -lc \
    'set -e; for f in /migrations/*.sql; do echo "Applying $f"; psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f"; done'
}

# -------------------------------------------------------------------
# showvsb — FULL backend health check
# -------------------------------------------------------------------
showvsb() {
  local COMPOSE_FILE="$(_vsb_compose_file)"
  local API_URL="http://localhost:8081"

  echo "🔍 VeriSphere backend health check"
  echo "--------------------------------"

  [ -f "$COMPOSE_FILE" ] || { echo "❌ docker-compose.yml not found at $COMPOSE_FILE"; return 1; }
  _vsb_load_env || return 1

  docker info >/dev/null 2>&1 || { echo "❌ docker daemon not running"; return 1; }
  echo "✅ docker running"

  docker compose -f "$COMPOSE_FILE" ps

  local PG_STATUS
  PG_STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null)
  [ "$PG_STATUS" = "healthy" ] || { echo "❌ postgres not healthy (status=$PG_STATUS)"; return 1; }
  echo "✅ postgres healthy"

  # Postgres connectivity (TCP; always uses password auth)
  if ! docker compose -f "$COMPOSE_FILE" exec -T postgres bash -lc \
    "PGPASSWORD='$POSTGRES_APP_PASSWORD' psql -h localhost -U '$POSTGRES_APP_USER' -d '$POSTGRES_DB' -c 'select 1;'" \
    >/dev/null 2>&1; then
    echo "❌ postgres app-user connection failed (TCP)"
    echo "   user=$POSTGRES_APP_USER db=$POSTGRES_DB"
    echo "   (debug) running the command to show error:"
    docker compose -f "$COMPOSE_FILE" exec -T postgres bash -lc \
      "PGPASSWORD='$POSTGRES_APP_PASSWORD' psql -h localhost -U '$POSTGRES_APP_USER' -d '$POSTGRES_DB' -c 'select 1;'" || true
    return 1
  fi
  echo "✅ postgres app-user auth OK"

  curl -sf "$API_URL/health" >/dev/null || { echo "❌ API /health failed"; return 1; }
  echo "✅ API /health OK"

  # Semantic pipeline test (will also trigger SC/CCS)
  curl -sf -X POST "$API_URL/claims/check-duplicate" \
    -H "Content-Type: application/json" \
    -d '{"claim_text":"showvsb semantic test"}' \
    >/dev/null || { echo "❌ semantic pipeline failed"; return 1; }

  echo "✅ semantic pipeline OK"
  echo
  echo "🟢 VeriSphere backend is FULLY healthy"
}

# -------------------------------------------------------------------
# startvsb — start / restart backend (non-destructive)
# -------------------------------------------------------------------
startvsb() {
  echo "🚀 Starting VeriSphere backend"
  echo "-------------------------------"

  local COMPOSE_FILE="$(_vsb_compose_file)"
  [ -f "$COMPOSE_FILE" ] || { echo "❌ docker-compose.yml not found at $COMPOSE_FILE"; return 1; }

  docker info >/dev/null 2>&1 || { echo "❌ docker daemon not running"; return 1; }
  _vsb_load_env || return 1
  echo "✅ environment loaded"

  if docker compose -f "$COMPOSE_FILE" ps --status running | grep -q semantic-dedupe; then
    echo "🔄 backend already running — restarting"
    docker compose -f "$COMPOSE_FILE" down || return 1
  else
    echo "ℹ️ backend not running"
  fi

  echo "🐳 docker compose up"
  docker compose -f "$COMPOSE_FILE" up -d --build || return 1

  echo "⏳ waiting for postgres to become healthy..."
  local STATUS=""
  for i in {1..40}; do
    STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null)
    if [ "$STATUS" = "healthy" ]; then
      echo "✅ postgres healthy"
      break
    fi
    sleep 1
  done
  [ "$STATUS" = "healthy" ] || { echo "❌ postgres failed to become healthy"; return 1; }

  _vsb_run_migrations || return 1

  echo
  echo "🟢 VeriSphere backend started"
}

# -------------------------------------------------------------------
# killvsb — stop backend (non-destructive)
# -------------------------------------------------------------------
killvsb() {
  local COMPOSE_FILE="$(_vsb_compose_file)"
  [ -f "$COMPOSE_FILE" ] || { echo "❌ docker-compose.yml not found at $COMPOSE_FILE"; return 1; }

  echo "🛑 Stopping VeriSphere backend"
  docker compose -f "$COMPOSE_FILE" down || return 1
  echo
  echo "🟡 VeriSphere backend stopped"
}

resetvsb() {
  local COMPOSE_FILE="$(_vsb_compose_file)"
  [ -f "$COMPOSE_FILE" ] || { echo "❌ docker-compose.yml not found"; return 1; }

  echo "🔥 RESETTING VeriSphere backend (DEV ONLY)"
  echo "------------------------------------------"
  echo "⚠️  This will DELETE ALL Postgres data."

  read -p "Type 'reset' to continue: " CONFIRM
  if [ "$CONFIRM" != "reset" ]; then
    echo "❌ aborted"
    return 1
  fi

  _vsb_load_env || return 1

  # 1) Hard stop + delete volumes
  docker compose -f "$COMPOSE_FILE" down -v || return 1

  # 2) Start ONLY postgres
  echo "🐘 starting postgres only"
  docker compose -f "$COMPOSE_FILE" up -d postgres || return 1

  # 3) Wait for postgres
  echo "⏳ waiting for postgres to become healthy..."
  local STATUS=""
  for i in {1..40}; do
    STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null)
    if [ "$STATUS" = "healthy" ]; then
      echo "✅ postgres healthy"
      break
    fi
    sleep 1
  done
  [ "$STATUS" = "healthy" ] || { echo "❌ postgres failed to become healthy"; return 1; }

  # 4) Run migrations (creates roles, tables, sequences)
  _vsb_run_migrations || return 1

  # 5) Start semantic-dedupe AFTER DB is ready
  echo "🧠 starting semantic-dedupe"
  docker compose -f "$COMPOSE_FILE" up -d semantic-dedupe || return 1

  echo
  echo "🟢 VeriSphere backend RESET complete"
}

