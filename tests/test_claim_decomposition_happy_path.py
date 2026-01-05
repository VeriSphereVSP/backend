from __future__ import annotations

import pytest

from .utils import http_post_json, assert_stable_4xx_or_200


def _call_decompose(base_url: str, path: str, text: str):
    url = base_url.rstrip("/") + path
    return http_post_json(url, {"text": text})


def test_decompose_splits_compound(claim_decompose_url: str, claim_decompose_decompose_path: str):
    """
    Expected behavior:
      - "A and B" splits into at least 2 atomic claims.
    """
    status, body, raw = _call_decompose(
        claim_decompose_url,
        claim_decompose_decompose_path,
        "The Earth orbits the Sun and the Moon orbits the Earth.",
    )

    # If not implemented yet, let it be optionally skipped.
    if status == 404:
        pytest.skip("claim-decompose endpoint not found; adjust CLAIM_DECOMPOSE_DECOMPOSE_PATH or implement it.")
    if status == 501:
        pytest.skip("claim-decompose not implemented (501).")

    assert status == 200, f"{status}: {raw[:300]}"
    assert isinstance(body, dict), raw[:200]
    # We accept either 'claims' or 'atomic_claims' key; normalize.
    claims = body.get("claims") or body.get("atomic_claims")
    assert isinstance(claims, list), body
    assert len(claims) >= 2, body


def test_decompose_atomic_is_stable(claim_decompose_url: str, claim_decompose_decompose_path: str):
    status, body, raw = _call_decompose(
        claim_decompose_url,
        claim_decompose_decompose_path,
        "The Earth orbits the Sun.",
    )
    if status in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")
    assert status == 200, f"{status}: {raw[:300]}"
    claims = body.get("claims") or body.get("atomic_claims")
    assert isinstance(claims, list)
    assert len(claims) >= 1

