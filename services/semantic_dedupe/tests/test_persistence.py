from app.db import get_or_create_claim_with_embedding


def test_embedding_reused(db_session, embedder):
    text = "Nuclear energy is safe."

    id1, created1 = get_or_create_claim_with_embedding(
        db_session,
        claim_text=text,
        embedder=embedder,
    )

    id2, created2 = get_or_create_claim_with_embedding(
        db_session,
        claim_text=text,
        embedder=embedder,
    )

    assert id1 == id2
    assert created1 is True
    assert created2 is False

