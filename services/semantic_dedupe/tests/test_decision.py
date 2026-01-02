from app.decision import classify_similarity, DedupeDecision


def test_duplicate():
    assert classify_similarity(0.95) == DedupeDecision.DUPLICATE


def test_probable_duplicate():
    assert classify_similarity(0.85) == DedupeDecision.PROBABLE_DUPLICATE


def test_related():
    assert classify_similarity(0.70) == DedupeDecision.RELATED


def test_distinct():
    assert classify_similarity(0.40) == DedupeDecision.DISTINCT

