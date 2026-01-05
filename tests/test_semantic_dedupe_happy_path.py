from __future__ import annotations

from .utils import http_post_json


def test_semantic_dedupe_new_claim(semantic_dedupe_url: str):
    status, body, text = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": "Nuclear energy produces low operational CO2 emissions.", "top_k": 5},
    )
    assert status == 200, f"{status}: {text[:300]}"
    assert isinstance(body, dict)
    assert "classification" in body
    assert body["classification"] in ("new", "near_duplicate", "duplicate")
    assert "claim_id" in body
    assert "hash" in body


def test_semantic_dedupe_same_claim_is_duplicate_or_near(semantic_dedupe_url: str):
    c = "The Earth orbits the Sun."
    status1, body1, _ = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": c, "top_k": 5},
    )
    assert status1 == 200
    status2, body2, text2 = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": c, "top_k": 5},
    )
    assert status2 == 200, f"{status2}: {text2[:300]}"
    # For identical text, content_hash should match, claim_id should match.
    assert body2["hash"] == body1["hash"]
    assert body2["claim_id"] == body1["claim_id"]

