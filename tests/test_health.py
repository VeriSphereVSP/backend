from __future__ import annotations

import pytest

from .utils import wait_for_health


def test_semantic_dedupe_health(semantic_dedupe_url: str):
    wait_for_health(semantic_dedupe_url, "/health")


def test_claim_decompose_health(claim_decompose_url: str, claim_decompose_health_path: str):
    """
    If claim-decompose isn't implemented yet (or path differs), this will fail.
    If you want it to be optional, set VSB_TEST_OPTIONAL_CLAIM_DECOMPOSE=1 and we skip.
    """
    import os
    optional = os.getenv("VSB_TEST_OPTIONAL_CLAIM_DECOMPOSE", "0") == "1"
    try:
        wait_for_health(claim_decompose_url, claim_decompose_health_path)
    except Exception as e:
        if optional:
            pytest.skip(f"claim-decompose health unavailable (optional): {e}")
        raise

