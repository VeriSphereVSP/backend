from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


def _try_load_backend_env() -> None:
    """
    Load backend/ops/compose/.env if present so running tests locally is easy.
    """
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "backend" / "ops" / "compose" / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_try_load_backend_env()


@pytest.fixture(scope="session")
def semantic_dedupe_url() -> str:
    return os.getenv("SEMANTIC_DEDUPE_URL", "http://localhost:8081")


@pytest.fixture(scope="session")
def claim_decompose_url() -> str:
    return os.getenv("CLAIM_DECOMPOSE_URL", "http://localhost:8090")


@pytest.fixture(scope="session")
def claim_decompose_decompose_path() -> str:
    return os.getenv("CLAIM_DECOMPOSE_DECOMPOSE_PATH", "/claims/decompose")


@pytest.fixture(scope="session")
def claim_decompose_health_path() -> str:
    return os.getenv("CLAIM_DECOMPOSE_HEALTH_PATH", "/healthz")


@pytest.fixture(scope="session")
def core_rpc_url() -> str | None:
    return os.getenv("CORE_RPC_URL") or None


@pytest.fixture(scope="session")
def core_addresses() -> dict:
    # Tests will skip unless these are present.
    return {
        "post_registry": os.getenv("CORE_POST_REGISTRY"),
        "stake_engine": os.getenv("CORE_STAKE_ENGINE"),
        "link_graph": os.getenv("CORE_LINK_GRAPH"),
        "protocol_views": os.getenv("CORE_PROTOCOL_VIEWS"),
    }

