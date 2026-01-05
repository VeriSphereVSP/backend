# VeriSphere Backend

This directory contains the **VeriSphere backend services** responsible for
AI-assisted claim ingestion and semantic normalization.

The backend is intentionally split into **small, composable services** that
together enforce a clean, adversarial-resistant claim pipeline.

---

## Architecture Overview

```
User Input
  ↓
Claim Decomposition (AI)
  ↓
Atomic Claims
  ↓
Semantic Deduplication
  ↓
Canonical Claims + Clusters
  ↓
(Postgres persistence)
```

### Services

| Service | Purpose | Default Port |
|------|--------|-------------|
| `claim-decompose` | Split user text into atomic claims | `8090` |
| `semantic-dedupe` | Detect duplicates & assign canonicals | `8081` |
| `postgres` | Persistent store (claims, clusters, embeddings) | `5432` |

All services are orchestrated via Docker Compose and managed with
`verisphere-backend.sh`.

---

## Operational Commands

From a shell where `backend/ops/shell/verisphere-backend.sh` is sourced:

```bash
startvsb   # start backend + wait for readiness
showvsb    # show status (non-blocking)
resetvsb   # destructive reset (DEV ONLY)
testvsb    # run full backend E2E test suite
killvsb    # stop backend
```

---

## API Conventions

- All APIs use **JSON**
- UTF-8 text only
- Deterministic behavior for identical inputs
- No silent failures
- Garbage input is allowed, but handled safely

---

# Claim Decomposition Service

**Base URL:** `http://localhost:8090`

## Health Check

### `GET /healthz`

```json
{ "ok": true }
```

## Decompose Claim

### `POST /claims/decompose`

```json
{
  "text": "Smoking causes cancer and reduces life expectancy."
}
```

Response:

```json
{
  "claims": [
    "Smoking causes cancer.",
    "Smoking reduces life expectancy."
  ]
}
```

---

# Semantic Deduplication Service

**Base URL:** `http://localhost:8081`

## Health Check

### `GET /health`

```json
{ "ok": true }
```

## Check Duplicate

### `POST /claims/check-duplicate`

```json
{
  "claim_text": "Nuclear energy is safe.",
  "top_k": 5
}
```

Example response:

```json
{
  "classification": "new",
  "claim_id": 42,
  "canonical_claim_id": 42,
  "cluster_id": 12
}
```

---

## End-to-End Example

1. Decompose input
2. Deduplicate each atomic claim independently

