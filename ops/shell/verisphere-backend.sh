#!/usr/bin/env bash
# VeriSphere backend helper functions
# Source from ~/.bashrc or ~/.bash_profile

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
_vsb_compose_dir() { echo "$HOME/verisphere/backend/ops/compose"; }
_vsb_compose_file() { echo "$(_vsb_compose_dir)/docker-compose.yml"; }
_vsb_env_file() { echo "$(_vsb_compose_dir)/.env"; }
_vsb_backend_dir() { echo "$HOME/verisphere/backend"; }
_vsb_tests_dir() { echo "$(_vsb_backend_dir)/tests"; }
_vsb_venv_dir() { echo "$(_vsb_backend_dir)/.venv-tests"; }

# ---------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------
_vsb_load_env() {
  local ENV_FILE="$(_vsb_env_file)"
  [ -f "$ENV_FILE" ] || { echo "❌ .env missing at $ENV_FILE"; return 1; }
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

_require_docker() {
  docker info >/dev/null 2>&1 || {
    echo "❌ docker daemon not running"
    return 1
  }
}

_is_any_service_running() {
  docker compose -f "$(_vsb_compose_file)" ps --status running -q 2>/dev/null | grep -q .
}

# ---------------------------------------------------------------------
# Wait helpers (bounded, never infinite)
# ---------------------------------------------------------------------
_wait_container_healthy() {
  local CONTAINER="$1"
  local MAX_TRIES="${2:-40}"
  local STATUS

  for _ in $(seq 1 "$MAX_TRIES"); do
    STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "missing")
    if [ "$STATUS" = "healthy" ]; then
      return 0
    fi
    sleep 1
  done

  echo "❌ $CONTAINER not healthy (status=$STATUS)"
  echo "   Try: docker logs $CONTAINER"
  return 1
}

_wait_http_ok() {
  local URL="$1"
  local LABEL="$2"
  local MAX_TRIES="${3:-10}"

  for _ in $(seq 1 "$MAX_TRIES"); do
    if curl -sf "$URL" >/dev/null 2>&1; then
      echo "✅ $LABEL healthy"
      return 0
    fi
    sleep 1
  done

  echo "❌ $LABEL did not respond at $URL"
  return 1
}

# ---------------------------------------------------------------------
# showvsb — OBSERVATIONAL ONLY (never waits)
# ---------------------------------------------------------------------
showvsb() {
  local COMPOSE="$(_vsb_compose_file)"

  _require_docker || return 1
  _vsb_load_env || return 1

  echo "🔍 VeriSphere backend status"
  echo "---------------------------"

  timeout 5 docker compose -f "$COMPOSE" ps || echo "⚠️ docker compose ps timed out"

  if ! _is_any_service_running; then
    echo
    echo "🟡 Backend is DOWN (no running services)"
    return 0
  fi

  echo

  local PG_STATUS
  PG_STATUS=$(docker inspect -f '{{.State.Health.Status}}' verisphere_postgres 2>/dev/null || echo "missing")
  if [ "$PG_STATUS" = "healthy" ]; then
    echo "✅ postgres healthy"
  else
    echo "❌ postgres not healthy (status=$PG_STATUS)"
    echo "   Try: docker logs verisphere_postgres"
  fi

  if curl -sf "http://localhost:${SEMANTIC_DEDUPE_PORT:-8081}/health" >/dev/null; then
    echo "✅ semantic-dedupe healthy"
  else
    echo "❌ semantic-dedupe unhealthy"
    echo "   Try: docker logs verisphere_semantic_dedupe"
  fi

  if curl -sf "http://localhost:${CLAIM_DECOMPOSE_PORT:-8090}/healthz" >/dev/null; then
    echo "✅ claim-decompose healthy"
  else
    echo "❌ claim-decompose unhealthy"
    echo "   Try: docker logs verisphere_claim_decompose"
  fi
}

# ---------------------------------------------------------------------
# startvsb — START + WAIT
# ---------------------------------------------------------------------
startvsb() {
  local COMPOSE="$(_vsb_compose_file)"

  _require_docker || return 1
  _vsb_load_env || return 1

  echo "🚀 Starting VeriSphere backend"
  docker compose -f "$COMPOSE" up -d --build || return 1

  echo "⏳ waiting for postgres..."
  _wait_container_healthy verisphere_postgres || return 1

  echo "🗄️ running migrations"
  docker compose -f "$COMPOSE" exec -T postgres bash -lc \
    'set -e; for f in /migrations/*.sql; do psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f"; done' \
    || return 1

  echo "⏳ waiting for semantic-dedupe..."
  _wait_http_ok \
    "http://localhost:${SEMANTIC_DEDUPE_PORT:-8081}/health" \
    "semantic-dedupe" \
    15 || return 1

  echo "⏳ waiting for claim-decompose..."
  _wait_http_ok \
    "http://localhost:${CLAIM_DECOMPOSE_PORT:-8090}/healthz" \
    "claim-decompose" \
    10 || return 1

  echo
  echo "🟢 VeriSphere backend started successfully"
}

# ---------------------------------------------------------------------
# killvsb — STOP ONLY
# ---------------------------------------------------------------------
killvsb() {
  local COMPOSE="$(_vsb_compose_file)"

  _require_docker || return 1
  docker compose -f "$COMPOSE" down || return 1
  echo "🟡 VeriSphere backend stopped"
}

# ---------------------------------------------------------------------
# resetvsb — DESTRUCTIVE (DEV ONLY)
# ---------------------------------------------------------------------
resetvsb() {
  local COMPOSE="$(_vsb_compose_file)"

  echo "🔥 RESETTING VeriSphere backend (DEV ONLY)"
  echo "⚠️  This will DELETE ALL Postgres data."

  read -r -p "Type 'reset' to continue: " CONFIRM
  [ "$CONFIRM" = "reset" ] || { echo "❌ aborted"; return 1; }

  _require_docker || return 1
  _vsb_load_env || return 1

  docker compose -f "$COMPOSE" down -v || return 1
  docker compose -f "$COMPOSE" up -d postgres || return 1

  echo "⏳ waiting for postgres..."
  _wait_container_healthy verisphere_postgres || return 1

  echo "🗄️ running migrations"
  docker compose -f "$COMPOSE" exec -T postgres bash -lc \
    'set -e; for f in /migrations/*.sql; do psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f"; done' \
    || return 1

  echo "🚀 starting services"
  docker compose -f "$COMPOSE" up -d semantic-dedupe claim-decompose || return 1

  echo "⏳ waiting for services..."
  _wait_http_ok "http://localhost:${SEMANTIC_DEDUPE_PORT:-8081}/health" "semantic-dedupe" 15 || return 1
  _wait_http_ok "http://localhost:${CLAIM_DECOMPOSE_PORT:-8090}/healthz" "claim-decompose" 10 || return 1

  echo
  echo "🟢 VeriSphere backend RESET complete"
}

# ---------------------------------------------------------------------
# testvsb — RUN FULL BACKEND E2E TEST SUITE
# ---------------------------------------------------------------------
testvsb() {
  _require_docker || return 1
  _vsb_load_env || return 1

  if ! _is_any_service_running; then
    echo "❌ Backend is not running. Start it first (startvsb or resetvsb)."
    return 1
  fi

  echo "🧪 Running VeriSphere backend E2E tests"
  echo "--------------------------------------"

  echo "🔎 verifying service health before tests"
  _wait_container_healthy verisphere_postgres 5 || return 1
  _wait_http_ok "http://localhost:${SEMANTIC_DEDUPE_PORT:-8081}/health" "semantic-dedupe" 5 || return 1
  _wait_http_ok "http://localhost:${CLAIM_DECOMPOSE_PORT:-8090}/healthz" "claim-decompose" 5 || return 1

  local VENV="$(_vsb_venv_dir)"
  local TESTS="$(_vsb_tests_dir)"

  [ -d "$TESTS" ] || {
    echo "❌ tests directory not found at $TESTS"
    return 1
  }

  if [ ! -d "$VENV" ]; then
    echo "🐍 creating test virtualenv"
    python3 -m venv "$VENV" || return 1
  fi

  # shellcheck disable=SC1090
  source "$VENV/bin/activate"

  echo "📦 installing test requirements"
  pip install -q --upgrade pip
  pip install -q -r "$TESTS/requirements.txt" || {
    deactivate
    return 1
  }

  echo "▶️ running pytest"
  pytest -q "$TESTS" || {
    deactivate
    echo "❌ E2E tests failed"
    return 1
  }

  deactivate
  echo
  echo "🟢 All VeriSphere backend E2E tests PASSED"
}

