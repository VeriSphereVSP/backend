from app.hashing import content_hash

def test_hash_deterministic():
    t = "Nuclear energy is safe."
    assert content_hash(t) == content_hash(t)

def test_hash_whitespace_insensitive():
    a = "Nuclear energy  is   safe."
    b = " nuclear energy is safe "
    assert content_hash(a) == content_hash(b)

def test_hash_case_insensitive():
    assert content_hash("SAFE") == content_hash("safe")

