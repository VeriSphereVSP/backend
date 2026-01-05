from __future__ import annotations

import pytest

from .utils import http_post_json, assert_stable_4xx_or_200


EDGE_CASES = [
    # Nonsense / garbage
    "asdf qwer zxcv !!!",
    "!!!!@@@@####",
    "the the the the the the the",
    "",
    "   ",
    # Opinion / subjective
    "Chocolate is the best flavor.",
    "That movie is amazing.",
    # Paradox / conundrum
    "This statement is false.",
    "Everything I say is a lie.",
    # Adversarial packing
    "Nuclear energy is safe (unlike renewables which kill millions).",
    "Vaccines are safe and dangerous depending on perspective.",
]


@pytest.mark.parametrize("text", EDGE_CASES)
def test_semantic_dedupe_edge_cases_do_not_500(semantic_dedupe_url: str, text: str):
    status, body, raw = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": text, "top_k": 5},
    )
    assert status < 500, f"Unexpected 5xx for input={text!r}: {status} {raw[:300]}"
    # Usually we expect 200, but allowing 4xx is ok if you add input validation later.
    assert status == 200 or 400 <= status < 500


def test_semantic_dedupe_deterministic_hash_normalization(semantic_dedupe_url: str):
    a = "Nuclear energy is safe."
    b = "  nuclear energy is safe  "
    status1, body1, _ = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": a, "top_k": 5},
    )
    status2, body2, _ = http_post_json(
        semantic_dedupe_url.rstrip("/") + "/claims/check-duplicate",
        {"claim_text": b, "top_k": 5},
    )
    # If you reject whitespace-only, adjust accordingly. For now, both should succeed.
    assert status1 == 200 and status2 == 200
    assert body1["hash"] == body2["hash"]

