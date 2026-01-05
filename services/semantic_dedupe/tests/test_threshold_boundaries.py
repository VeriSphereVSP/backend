from app.api import classify

def test_duplicate_exact_threshold():
    assert classify(0.95) == "duplicate"

def test_near_duplicate_exact_threshold():
    assert classify(0.85) == "near_duplicate"

def test_below_near_duplicate():
    assert classify(0.8499) == "new"

