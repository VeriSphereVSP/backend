from __future__ import annotations

import pytest

from .utils import http_post_json


def test_attack_claim_packing_should_split_and_not_merge_topics(
    claim_decompose_url: str,
    claim_decompose_decompose_path: str,
):
    """
    This is a structural/attack test: the system must not keep packed claims as one atomic unit.
    """
    url = claim_decompose_url.rstrip("/") + claim_decompose_decompose_path
    text = "Nuclear energy is safe (unlike renewables which kill millions) and the sky is blue."
    status, body, raw = http_post_json(url, {"text": text})

    if status in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")

    assert status == 200, f"{status}: {raw[:300]}"
    claims = body.get("claims") or body.get("atomic_claims") or []
    assert isinstance(claims, list)
    # We expect at least 2 claims from the explicit 'and'
    assert len(claims) >= 2


def test_attack_nonsense_should_not_create_massive_output(
    claim_decompose_url: str,
    claim_decompose_decompose_path: str,
):
    """
    Resource-safety: nonsense must not explode into huge lists.
    """
    url = claim_decompose_url.rstrip("/") + claim_decompose_decompose_path
    text = "asdf " * 4000
    status, body, raw = http_post_json(url, {"text": text})

    if status in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")

    assert status < 500, f"{status}: {raw[:200]}"
    if status == 200:
        claims = (body or {}).get("claims") or (body or {}).get("atomic_claims") or []
        assert len(claims) <= 50, f"unexpectedly huge output: {len(claims)}"

