# VeriSphere Backend Tests

This suite validates:
- Service health and readiness
- Semantic dedupe (happy path + edge cases)
- Claim decomposition (happy path + edge cases)
- Integration pipeline (decompose -> dedupe per atomic claim)
- Attack vector tests (claim packing / nonsense pollution / stability)
- Scaffold for Core<->Backend orchestration (claims, stakes, links)

## Quickstart

1) Start the backend services:
   - startvsb / resetvsb (from ops shell helpers)

2) Run tests from repo root:
   python3 -m venv .venv-tests
   source .venv-tests/bin/activate
   pip install -r backend/tests/requirements.txt
   pytest -q backend/tests

## Configuration

Tests read env vars (and optionally load `backend/ops/compose/.env` if present):

- SEMANTIC_DEDUPE_URL (default http://localhost:8081)
- CLAIM_DECOMPOSE_URL  (default http://localhost:8090)
- CLAIM_DECOMPOSE_DECOMPOSE_PATH (default /claims/decompose)
- CLAIM_DECOMPOSE_HEALTH_PATH (default /health)

Core integration scaffold (tests auto-skip unless set):
- CORE_RPC_URL
- CORE_POST_REGISTRY
- CORE_STAKE_ENGINE
- CORE_LINK_GRAPH
- CORE_PROTOCOL_VIEWS

## OpenAI requirement?

Not required for this test harness.

If semantic-dedupe is configured with EMBEDDINGS_PROVIDER=stub, it runs without OpenAI.
Claim-decompose tests will skip if the endpoint is missing/unimplemented.

