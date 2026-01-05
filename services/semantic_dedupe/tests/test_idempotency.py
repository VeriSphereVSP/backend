def test_assign_cluster_idempotent(db_session, embedder):
    from app.db import assign_claim_to_cluster

    db_session.execute(
        "INSERT INTO claim (claim_id, claim_text, content_hash) VALUES (1,'a','ha')"
    )
    db_session.commit()

    r1 = assign_claim_to_cluster(
        db_session,
        claim_id=1,
        best_match_claim_id=None,
        best_match_similarity=0.0,
        join_threshold=0.8,
    )

    r2 = assign_claim_to_cluster(
        db_session,
        claim_id=1,
        best_match_claim_id=None,
        best_match_similarity=0.0,
        join_threshold=0.8,
    )

    assert r1["cluster_id"] == r2["cluster_id"]
    assert r2["assigned"] is False

