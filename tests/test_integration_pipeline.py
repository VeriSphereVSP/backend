from __future__ import annotations

import pytest

from .utils import http_post_json


def test_decompose_then_dedupe_each_atomic(
    semantic_dedupe_url: str,
    claim_decompose_url: str,
    claim_decompose_decompose_path: str,
):
    """
    Integration invariant:
      - Decomposition produces atomic claims.
      - Each atomic claim can be fed into semantic dedupe without 5xx.
    """
    decompose_url = claim_decompose_url.rstrip("/") + claim_decompose_decompose_path
    d_status, d_body, d_raw = http_post_json(decompose_url, {"text": "A causes B and C causes D."})

    if d_status in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")

    assert d_status == 200, f"{d_status}: {d_raw[:300]}"
    claims = d_body.get("claims") or d_body.get("atomic_claims") or []
    assert isinstance(claims, list)
    assert len(claims) >= 2

    for atomic in claims:
        # Accept either {"text": "..."} objects or raw strings
        if isinstance(atomic, dict):
            t = atomic.get("claim") or atomic.get("text") or ""
        else:
            t = str(atomic)

        s_status, s_body, s_raw = http_post_json(
            semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
            {"claim_text": t, "top_k": 5},
        )
        assert s_status < 500, f"dedupe 5xx for atomic={t!r}: {s_status} {s_raw[:200]}"
        assert s_status == 200 or 400 <= s_status < 500

