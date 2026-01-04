#!/usr/bin/env bash
# VeriSphere backend helper functions
# Source this file from ~/.bashrc or ~/.bash_profile
#
# -------------------------------------------------------------------
# showvsb — FULL backend health check (FINAL)
# -------------------------------------------------------------------
#
showvsb() {
  local COMPOSE_DIR="$HOME/verisphere/backend/ops/compose"
  local COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
  local ENV_FILE="$COMPOSE_DIR/.env"
  local API_URL="http://localhost:8081"

  echo "🔍 VeriSphere backend health check"
  echo "--------------------------------"

  if [ ! -f "$COMPOSE_FILE" ] || [ ! -f "$ENV_FILE" ]; then
    echo "❌ compose config missing"
    return 1
  fi

  set -a
  source "$ENV_FILE"
  set +a

  docker info >/dev/null 2>&1 || {
    echo "❌ docker not running"
    return 1
  }
  echo "✅ docker running"

  docker compose -f "$COMPOSE_FILE" ps

  local PG_STATUS
  PG_STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null)
  [ "$PG_STATUS" = "healthy" ] || {
    echo "❌ postgres not healthy"
    return 1
  }
  echo "✅ postgres healthy"

  # 🔑 FORCE TCP AUTH
  if ! docker compose -f "$COMPOSE_FILE" exec -T postgres bash -lc \
    "PGPASSWORD='$POSTGRES_APP_PASSWORD' psql -h localhost -U '$POSTGRES_APP_USER' -d '$POSTGRES_DB' -c 'select 1;'" \
    >/dev/null; then
    echo "❌ postgres app-user connection failed (TCP)"
    return 1
  fi
  echo "✅ postgres app-user auth OK"

  curl -sf "$API_URL/health" >/dev/null || {
    echo "❌ API /health failed"
    return 1
  }
  echo "✅ API /health OK"

  curl -sf -X POST "$API_URL/claims/check-duplicate" \
    -H "Content-Type: application/json" \
    -d '{"claim_text":"showvsb semantic test"}' \
    >/dev/null || {
    echo "❌ semantic pipeline failed"
    return 1
  }

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

  local ORIG_PWD="$PWD"
  local COMPOSE_DIR="$HOME/verisphere/backend/ops/compose"
  local COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
  trap 'cd "$ORIG_PWD"' RETURN

  if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ docker-compose.yml not found at $COMPOSE_FILE"
    return 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "❌ docker daemon not running"
    return 1
  fi

  if [ ! -f "$COMPOSE_DIR/.env" ]; then
    echo "❌ .env missing in $COMPOSE_DIR"
    return 1
  fi

  set -a
  source "$COMPOSE_DIR/.env"
  set +a
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
  for i in {1..30}; do
    STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null)
    if [ "$STATUS" = "healthy" ]; then
      echo "✅ postgres healthy"
      break
    fi
    sleep 1
  done

  if [ "$STATUS" != "healthy" ]; then
    echo "❌ postgres failed to become healthy"
    return 1
  fi

  if [ -d "$COMPOSE_DIR/../postgres/migrations" ]; then
    echo "🗄️ running migrations"
    docker compose -f "$COMPOSE_FILE" exec -T postgres bash -lc '
      for f in /migrations/*.sql; do
        echo "Applying $f"
         psql -U postgres -d "$POSTGRES_DB" -f "$f"
      done 
    '
  fi

  echo
  echo "🟢 VeriSphere backend started"
}

# -------------------------------------------------------------------
# killvsb — stop backend (non-destructive)
# -------------------------------------------------------------------
killvsb() {
  local COMPOSE_DIR="$HOME/verisphere/backend/ops/compose"
  local COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"

  if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ docker-compose.yml not found"
    return 1
  fi

  echo "🛑 Stopping VeriSphere backend"
  docker compose -f "$COMPOSE_FILE" down || return 1

  echo
  echo "🟡 VeriSphere backend stopped"
}

# -------------------------------------------------------------------
# resetvsb — DEV ONLY: deletes Postgres volume
# -------------------------------------------------------------------
resetvsb() {
  local COMPOSE_DIR="$HOME/verisphere/backend/ops/compose"
  local COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"

  echo "🔥 RESETTING VeriSphere backend (DEV ONLY)"
  echo "------------------------------------------"
  echo "⚠️  This will DELETE ALL Postgres data."

  read -p "Type 'reset' to continue: " CONFIRM
  if [ "$CONFIRM" != "reset" ]; then
    echo "❌ aborted"
    return 1
  fi

  docker compose -f "$COMPOSE_FILE" down -v || return 1
  docker compose -f "$COMPOSE_FILE" up -d --build || return 1

  echo
  echo "🟢 VeriSphere backend RESET complete"
}

