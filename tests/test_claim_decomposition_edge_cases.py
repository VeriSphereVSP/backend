from __future__ import annotations

import pytest

from .utils import http_post_json, assert_stable_4xx_or_200


EDGE_CASES = [
    # Nonsense
    "asdf qwer zxcv !!!",
    "!!!!@@@@####",
    "the the the the the",
    "",
    "   ",
    # Opinion
    "Chocolate is the best flavor.",
    # Paradox
    "This statement is false.",
    # Adversarial packing
    "Nuclear energy is safe (unlike renewables which kill millions).",
]


@pytest.mark.parametrize("text", EDGE_CASES)
def test_decompose_edge_cases_no_500(claim_decompose_url: str, claim_decompose_decompose_path: str, text: str):
    url = claim_decompose_url.rstrip("/") + claim_decompose_decompose_path
    status, body, raw = http_post_json(url, {"text": text})

    if status in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")
    assert_stable_4xx_or_200(status)

    if status == 200:
        # If your decomposition service chooses to output [] for garbage, that's OK.
        claims = (body or {}).get("claims") or (body or {}).get("atomic_claims") or []
        assert isinstance(claims, list)


def test_decompose_deterministic_output_same_input(claim_decompose_url: str, claim_decompose_decompose_path: str):
    url = claim_decompose_url.rstrip("/") + claim_decompose_decompose_path
    text = "The Earth orbits the Sun and the Moon orbits the Earth."
    s1, b1, _ = http_post_json(url, {"text": text})
    s2, b2, _ = http_post_json(url, {"text": text})

    if s1 in (404, 501) or s2 in (404, 501):
        pytest.skip("claim-decompose missing/unimplemented.")
    assert s1 == 200 and s2 == 200
    # Deterministic requirement: exact match is ideal; if your service includes timestamps, you can normalize later.
    assert b1 == b2

