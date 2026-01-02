from app.similarity import cosine_similarity

def test_similarity_identity():
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == 1.0

def test_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-12

def test_similarity_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert cosine_similarity(a, b) == -1.0

